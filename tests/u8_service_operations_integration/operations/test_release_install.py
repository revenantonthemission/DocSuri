"""`docsuri-release install | rollback` (U8 plan Step 38; cicd-pipeline § 5–6 and § 11),
under a temporary prefix with a fake GitHub API and the realm driver: service control and
tunnel routing are the composed realm's own bound operations on the journey's own state,
and the ledger is a real one in the test's folder. Nothing reaches GitHub or this Mac.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import io
import json
import os
import secrets
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import yaml

from backend.modules.operations.cutover import Cutover
from backend.u8_policy import SYNTHETIC_OPERATIONS
from docsuri_ops import release
from docsuri_ops.arrangement import manifest
from docsuri_ops.arrangement.paths import ArrangementPaths
from docsuri_ops.arrangement.render import FIXED_PROGRAMS
from docsuri_ops.release import Refused, ReleaseInstall, ReleasePlatform
from tests.u8_service_operations_integration import arrangement_flows as af
from tests.u8_service_operations_integration import platform_flows as pf
from tests.u8_service_operations_integration import recovery_flows as rf

ROOT = Path(__file__).resolve().parents[3]
LABELS = tuple(f"dev.docsuri.u8.run.{name}" for name in ("host", "workers", "scheduler"))
# The complete verification's check names follow the module (the infrastructure re-check's
# R-13); `LANE_JOBS` are the workflow's job ids, which the other lanes also report as their
# unnamed jobs' check names.
NAMES = release.COMPLETE_VERIFICATION
LANE_JOBS = ("shared-contracts", "frontend", "backend", "browser")


def tag_of() -> str:
    return f"v2.{secrets.randbelow(9000) + 1}.{secrets.randbelow(9000) + 1}"


def workspace() -> tuple[bytes, str]:
    files = {"index.html": b"<!doctype html>", "maintenance.html": b"<p>notice</p>",
             "privacy.html": b"<p>privacy</p>", "terms.html": b"<p>terms</p>",
             "assets/app-1a2b3c.js": b"console.log(1)"}
    listing = {"version": 1, "files": [
        {"path": name, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
         "contentHashed": name.startswith("assets/")} for name, data in files.items()]}
    archive = af.tar_of({**files, ".docsuri-build.json": json.dumps(listing).encode()})
    return archive, hashlib.sha256(archive).hexdigest()


class GitHub:
    def __init__(self, tag: str):
        self.commit = secrets.token_hex(20)
        self.tags = {tag: {"sha": self.commit, "annotated": True}}
        self.main = {self.commit}
        self.runs = [{"name": name, "status": "completed", "conclusion": "success", "id": index,
                      "app": "github-actions"} for index, name in enumerate(NAMES)]
        self.archive, digest = workspace()
        self.assets = {release.WORKSPACE_ASSET: self.archive,
                       release.WORKSPACE_DIGEST_ASSET: f"{digest}  {release.WORKSPACE_ASSET}\n"
                       .encode()}

    def tag(self, tag):
        return self.tags.get(tag)

    def on_main(self, sha):
        return sha in self.main

    def check_runs(self, sha):
        return list(self.runs)

    def asset(self, tag, name):
        return self.assets[name]


@dataclasses.dataclass
class Stage:
    paths: ArrangementPaths
    github: GitHub
    platform: ReleasePlatform
    install: ReleaseInstall
    journey: pf.Journey
    tag: str
    clock: object
    calls: list
    state: dict

    def link(self, name: str = "release") -> str:
        return Path(os.readlink(self.paths.prefix / name)).name


def stage_for(tmp_path, realm, *, version: int = 1, ledger=None, rehearsal: str | None = None,
              clock=None, journey=None, operator=None, labels: tuple[str, ...] = LABELS,
              **journey_config) -> Stage:
    """The release command under a temporary prefix. `clock` (an advancing test clock),
    `journey`, `operator` and `labels` let another stage's realm share it: the production
    cutover tests run the release command and the cutover tool on one ledger and one
    realm's v2."""
    tag = tag_of()
    paths = ArrangementPaths.under(tmp_path / "Library" / "DocSuri")
    paths.releases.mkdir(parents=True)
    current = paths.releases / "v2.0.0"
    (current / "ops" / "bin").mkdir(parents=True)
    os.symlink(current, paths.release)
    (paths.releases / "v1.9.9-junk").mkdir()
    moments = {"now": af.NOW}
    state = {"memory": 16 * 1024**3, "rate": 3.0, "migrate": {"applied": []},
             "performance": {"passed": True}, "installer": {"failed": None},
             "ready_on": {tag, "v2.0.0"}, "probe": True, "version": version}
    calls: list = []

    def now():
        return moments["now"] if clock is None else clock()

    def clone(tag_name: str, folder: Path) -> None:
        calls.append(("clone", tag_name))
        (folder / "ops" / "bin").mkdir(parents=True)
        for name in FIXED_PROGRAMS:
            (folder / "ops" / "bin" / name).write_text("#!/usr/bin/false\n")
        templates = folder / "ops/src/docsuri_ops/arrangement/templates"
        templates.mkdir(parents=True)
        (templates / "VERSION").write_text(f"{state['version']}\n")

    def sync(folder: Path) -> None:
        calls.append(("sync", folder.name))
        (folder / ".venv" / "lib" / "python3.13" / "site-packages").mkdir(parents=True)

    def run_installer(folder: Path) -> dict:
        calls.append(("installer", folder.name))
        assert manifest.marker(paths) is not None  # the change runs under the marker
        recorded = manifest.Manifest(state["version"])
        manifest.write_manifest(paths, recorded, clock=now)
        return dict(state["installer"])

    def sleep(seconds: float) -> None:
        if clock is not None:
            clock.advance(seconds)
            return
        moments["now"] = moments["now"] + dt.timedelta(seconds=seconds)

    def ready() -> bool:
        return Path(os.readlink(paths.release)).name in state["ready_on"]

    if journey is None:
        journey = pf.journey(tmp_path, realm, mode="live", admission="open",
                             rehearsal=rehearsal, **journey_config)
    ledger = ledger or rf.open_ledger(tmp_path, now)
    github = GitHub(tag)
    # The base release carries its identity, as every staged release does: a rollback
    # refuses a kept folder whose identity cannot be read (your decision of 2026-10-26,
    # "Reuse the kept folder").
    release.write_identity(current, "v2.0.0", github.commit, owner_uid=os.getuid())
    platform = ReleasePlatform(
        github=github, clone=clone, sync=sync, confirm=lambda shown: shown["shortHash"],
        ledger=ledger, operator=operator or journey.operator(ledger=ledger, clock=now),
        run_installer=run_installer,
        migrate=lambda folder: dict(state["migrate"]),
        performance=lambda folder, commit: calls.append(("performance", commit)) or dict(
            state["performance"]),
        memory_available=lambda: state["memory"], request_rate=lambda: state["rate"],
        isolation=lambda: {"passed": True, "checkedAt": now().isoformat()},
        disk_free=lambda: 500 * 1024**3, ready=ready, probe=lambda: state["probe"],
        backup=lambda tag_name, key: {"integrity": "passed", "backupId": str(uuid4())},
        mode=lambda: "live", v2_labels=labels, sleep=sleep, policy=SYNTHETIC_OPERATIONS,
    )
    manifest.write_manifest(paths, manifest.Manifest(1), clock=now)
    install = ReleaseInstall(paths, platform, clock=now)
    return Stage(paths, github, platform, install, journey, tag, now, calls, state)


@pytest.fixture
def stage(tmp_path, realm):
    value = stage_for(tmp_path, realm)
    yield value
    value.platform.ledger.close()


def services(stage) -> dict:
    found = {}
    for label in LABELS:
        state = stage.journey.read_state("services", f"{label}.json")
        found[label.rsplit(".", 1)[-1]] = None if state is None else state["state"]
    return found


def refused(stage, reason: str, tag: str | None = None) -> Refused:
    with pytest.raises(Refused) as raised:
        stage.install.install(tag or stage.tag)
    assert raised.value.reason == reason, raised.value.facts
    return raised.value


def untouched(stage) -> None:
    assert not (stage.paths.releases / stage.tag).exists()
    assert stage.link() == "v2.0.0" and services(stage) == dict.fromkeys(
        ("host", "workers", "scheduler"))
    assert stage.journey.tunnel() is None and stage.install.records.get(stage.tag) is None


# --- 1. refusals before anything changes -------------------------------------------------------


def test_it_refuses_an_unverified_commit_a_lightweight_tag_a_tag_off_main_and_a_wrong_hash(
    stage
):
    stage.github.runs[-1] = {**stage.github.runs[-1], "conclusion": "failure"}
    assert refused(stage, "complete-verification-not-passed").facts == {"checks": [NAMES[-1]]}
    stage.github.runs = stage.github.runs[:-1]
    assert refused(stage, "complete-verification-not-passed").facts == {"checks": [NAMES[-1]]}
    stage.github.runs.append({"name": NAMES[-1], "status": "completed",
                              "conclusion": "success", "id": 9, "app": "github-actions"})
    stage.github.tags[stage.tag]["annotated"] = False
    refused(stage, "tag-not-annotated")
    stage.github.tags[stage.tag]["annotated"] = True
    stage.github.main.clear()
    refused(stage, "tag-not-on-main")
    stage.github.main.add(stage.github.commit)
    stage.platform.confirm = lambda shown: shown["shortHash"][:-1] + "x"
    refused(stage, "short-hash-differs")
    refused(stage, "tag-unknown", tag="v9.9.9")
    with pytest.raises(Refused, match="tag-outside-its-form"):
        stage.install.install("main")
    untouched(stage)


# --- 1a. the complete verification's own check names (the infrastructure re-check's R-13) ------


def gate(tmp_path) -> tuple[release.Stager, GitHub, str]:
    """The install's check-run gate alone: a `Stager` over the fake GitHub, whose clone and
    sync fail the test if called."""
    tag = tag_of()
    github = GitHub(tag)

    def never(*_arguments) -> None:
        pytest.fail("the gate cloned or synced")

    paths = ArrangementPaths.under(tmp_path / "Library" / "DocSuri")
    return release.Stager(paths, github, never, never), github, tag


def other_lanes(conclusion: str) -> list[dict]:
    """U6's four unnamed jobs (ids 40-43) and U2's unnamed `frontend` (id 44), last."""
    jobs = [*LANE_JOBS, "frontend"]
    return [{"name": name, "status": "completed", "conclusion": conclusion, "id": 40 + index,
             "app": "github-actions"} for index, name in enumerate(jobs)]


def refused_at_gate(stager: release.Stager, tag: str) -> Refused:
    with pytest.raises(Refused) as raised:
        stager.checked(tag)
    return raised.value


def test_another_workflows_job_of_the_same_id_neither_passes_nor_masks_the_complete_verification(
    tmp_path,
):
    stager, github, tag = gate(tmp_path)
    lane = list(github.runs)
    # 1. The lane passed and every other lane's same-id job failed: only the lane counts.
    github.runs = [*lane, *other_lanes("failure")]
    found, runs = stager.checked(tag)
    assert found["sha"] == github.commit
    assert [run["id"] for run in runs] == [2, 3, 1, 0]
    assert all(run["name"] in NAMES for run in runs)
    # 2. The lane's frontend failed; U2's and U6's passing `frontend` do not stand in.
    github.runs = [*lane, *other_lanes("success")]
    github.runs[1] = {**github.runs[1], "conclusion": "failure"}
    problem = refused_at_gate(stager, tag)
    assert problem.reason == "complete-verification-not-passed"
    assert problem.facts == {"checks": ["U8 complete / frontend"]}
    # 3. No run of the lane at all: the other lanes' passing runs are no evidence.
    github.runs = other_lanes("success")
    problem = refused_at_gate(stager, tag)
    assert problem.reason == "complete-verification-not-passed"
    assert problem.facts == {"checks": list(NAMES)}


def test_a_run_of_a_lane_name_from_another_app_is_refused_as_ambiguous(tmp_path):
    stager, github, tag = gate(tmp_path)
    lane = list(github.runs)
    foreign = {"name": NAMES[3], "app": "another-app", "status": "completed",
               "conclusion": "success", "id": 30}
    unnamed = {key: value for key, value in foreign.items() if key != "app"}
    failed = {**foreign, "conclusion": "failure"}
    for fifth in (foreign, unnamed, failed):
        github.runs = [*lane, fifth]
        problem = refused_at_gate(stager, tag)
        assert problem.reason == "complete-verification-ambiguous", fifth
        assert problem.facts == {"checks": [NAMES[3]]}, fifth
    github.runs = [{**lane[0], "app": "another-app"}, *lane[1:], foreign]
    problem = refused_at_gate(stager, tag)
    assert problem.reason == "complete-verification-ambiguous"
    assert problem.facts == {"checks": [NAMES[0], NAMES[3]]}


def test_repeated_runs_of_a_lane_name_are_read_together_and_each_must_pass(tmp_path):
    stager, github, tag = gate(tmp_path)
    lane = list(github.runs)
    second = {"name": NAMES[1], "status": "completed", "conclusion": "success", "id": 7,
              "app": "github-actions"}
    # 1. A second passing run, as the first release's `main` push leaves one.
    github.runs = [*lane, second]
    _, runs = stager.checked(tag)
    assert [run["id"] for run in runs] == [2, 3, 1, 7, 0]

    def refused_for_frontend(runs: list[dict]) -> None:
        github.runs = runs
        problem = refused_at_gate(stager, tag)
        assert problem.reason == "complete-verification-not-passed", runs
        assert problem.facts == {"checks": [NAMES[1]]}, runs

    # 2. The second run failed, listed after and before the passing id 1.
    failed = {**second, "conclusion": "failure"}
    refused_for_frontend([*lane, failed])
    refused_for_frontend([lane[0], failed, *lane[1:]])
    # 3. Still in progress.
    refused_for_frontend([lane[0], {**second, "status": "in_progress", "conclusion": None},
                          *lane[1:]])
    # 4. Every other conclusion counts as not passed, a cancelled run included.
    for conclusion in ("cancelled", "skipped", "neutral", "timed_out", "action_required",
                       "stale", "startup_failure"):
        refused_for_frontend([lane[0], {**second, "conclusion": conclusion}, *lane[1:]])
    # 5. A run without an id sorts after the other run of its name.
    no_id = {"name": NAMES[2], "status": "completed", "conclusion": "success",
             "app": "github-actions"}
    github.runs = [lane[0], lane[1], no_id, *lane[2:]]
    _, runs = stager.checked(tag)
    assert [run.get("id") for run in runs] == [2, None, 3, 1, 0]


def test_step_0_shows_every_run_of_the_lane_names_and_preflight_records_each(stage):
    stage.github.runs += [
        {"name": NAMES[0], "status": "completed", "conclusion": "success", "id": 9,
         "app": "github-actions"},
        {"name": "frontend", "status": "completed", "conclusion": "failure", "id": 20,
         "app": "github-actions"},
    ]

    def entry(name: str, run_id: int) -> dict:
        return {"name": name, "app": "github-actions", "status": "completed",
                "conclusion": "success", "id": run_id}

    assert stage.install.show(stage.tag)["verification"] == [
        entry("U8 complete / backend", 2), entry("U8 complete / browser", 3),
        entry("U8 complete / frontend", 1), entry("U8 complete / shared-contracts", 0),
        entry("U8 complete / shared-contracts", 9)]
    result = stage.install.install(stage.tag)
    assert result["state"] == "installed", result
    run_id = result["verification"]["verificationRunId"]
    evidence = stage.paths.control / "releases" / f"verification-run-{run_id}.json"
    recorded = json.loads(evidence.read_bytes())
    assert recorded["passed"] is True
    assert recorded["checkRuns"] == [
        ["U8 complete / backend", 2], ["U8 complete / browser", 3],
        ["U8 complete / frontend", 1], ["U8 complete / shared-contracts", 0],
        ["U8 complete / shared-contracts", 9]]


def reported_jobs(folder: Path) -> dict[str, dict[str, str]]:
    """Each workflow file directly in `folder` (GitHub reads no deeper): its jobs, each by
    the name GitHub reports for it, the job's `name:` or else its id. A document with no
    `jobs` mapping has no jobs."""
    found: dict[str, dict[str, str]] = {}
    for path in sorted([*folder.glob("*.yml"), *folder.glob("*.yaml")]):
        document = yaml.safe_load(path.read_text())
        jobs = document.get("jobs") if isinstance(document, dict) else None
        found[path.name] = {
            str(job_id): str(job["name"]) if isinstance(job, dict) and job.get("name")
            else str(job_id)
            for job_id, job in (jobs.items() if isinstance(jobs, dict) else ())}
    return found


LANE_WORKFLOW = "u8-complete-verification.yml"


def _says_u8_complete(text: str) -> bool:
    return "u8 complete" in text.lower().replace("-", " ").replace("_", " ")


def clashes(folder: Path) -> list[tuple[str, str, str]]:
    """Each job outside the lane's workflow that reports one of the lane's names, or whose
    `name:` or id says `u8 complete`, as (file, job id, reported name)."""
    return [(name, job_id, reported)
            for name, jobs in reported_jobs(folder).items() if name != LANE_WORKFLOW
            for job_id, reported in jobs.items()
            if reported in NAMES or _says_u8_complete(reported) or _says_u8_complete(job_id)]


def lane_names_problems(folder: Path) -> list[str]:
    """What is wrong with the lane's own reported names."""
    workflow = yaml.safe_load((folder / LANE_WORKFLOW).read_text())
    problems = [f"{job_id}: no name" for job_id, job in workflow["jobs"].items()
                if not (isinstance(job, dict) and job.get("name"))]
    reported = reported_jobs(folder)[LANE_WORKFLOW]
    if reported != dict(zip(LANE_JOBS, release.COMPLETE_VERIFICATION, strict=True)):
        problems.append(f"reports {reported}")
    if len(set(reported.values())) != len(reported):
        problems.append("names repeat")
    problems += [f"{job_id}: {name}" for job_id, name in reported.items()
                 if not name.startswith("U8 complete / ") or "(" in name or "${{" in name]
    return problems


def test_the_complete_verification_reports_names_no_other_workflow_reports(tmp_path):
    workflows = ROOT / ".github" / "workflows"
    assert lane_names_problems(workflows) == []
    assert clashes(workflows) == []
    lane_text = (workflows / LANE_WORKFLOW).read_text()

    def planted(name: str, extra: dict[str, str]) -> Path:
        folder = tmp_path / name
        folder.mkdir()
        (folder / LANE_WORKFLOW).write_text(lane_text)
        for file_name, text in extra.items():
            (folder / file_name).write_text(text)
        return folder

    named = planted("named", {"planted.yml": "jobs:\n  check:\n    name: U8 complete / frontend\n"
                                             "    runs-on: ubuntu-24.04\n"})
    assert clashes(named) == [("planted.yml", "check", "U8 complete / frontend")]
    by_id = planted("by-id", {"planted.yml": "jobs:\n  u8-complete-backend:\n"
                                             "    runs-on: ubuntu-24.04\n"})
    assert clashes(by_id) == [("planted.yml", "u8-complete-backend", "u8-complete-backend")]
    bare = planted("bare", {"planted.yml": "jobs:\n  frontend:\n    runs-on: ubuntu-24.04\n"})
    assert clashes(bare) == [] and lane_names_problems(bare) == []
    empty = planted("empty", {"planted.yml": "name: nothing to run\non: push\n"})
    assert clashes(empty) == [] and reported_jobs(empty)["planted.yml"] == {}
    unnamed = planted("unnamed", {})
    workflow = yaml.safe_load(lane_text)
    del workflow["jobs"]["frontend"]["name"]
    (unnamed / LANE_WORKFLOW).write_text(yaml.safe_dump(workflow))
    assert reported_jobs(unnamed)[LANE_WORKFLOW]["frontend"] == "frontend"
    assert "frontend: no name" in lane_names_problems(unnamed)


# --- 2. the workspace build's digest -----------------------------------------------------------


def test_it_refuses_a_workspace_build_whose_digest_differs(stage):
    stage.github.assets[release.WORKSPACE_DIGEST_ASSET] = b"0" * 64 + b"  x\n"
    refused(stage, "workspace-build-digest-differs")
    untouched(stage)
    assert ("clone", stage.tag) in stage.calls  # staged, then deleted


def test_it_refuses_a_build_that_breaks_its_own_manifest(tmp_path, stage):
    folder = tmp_path / "dist-check"
    folder.mkdir()
    archive, digest = workspace()
    release.unpack_workspace(archive, digest, folder)
    dist = folder / "frontend" / "dist"
    (dist / "privacy.html").write_text("changed")
    with pytest.raises(Refused, match="build-file-differs"):
        release.check_build_manifest(dist)
    (dist / ".docsuri-build.json").write_text("{}")
    with pytest.raises(Refused, match="build-manifest-form"):
        release.check_build_manifest(dist)


# --- 3. the live exclusion ------------------------------------------------------------------------


class Records:
    """A ledger holding exactly the records one case states."""

    def __init__(self, **kinds):
        self.kinds = {kind.replace("_", "-"): items for kind, items in kinds.items()}

    def records(self, kind):
        return list(self.kinds.get(kind, []))

    def get(self, kind, key):
        return None

    def close(self):
        pass


@pytest.mark.parametrize("ledger,reason", [
    (Records(recovery_request=[{"operation": "restore.production", "environment": "live",
                                "state": "running"}]), "production-restore-active"),
    (Records(cutover_record=[{"state": "switching"}]), "cutover-switching"),
    (Records(cutover_record=[{"state": "aborting"}]), "cutover-aborting"),
    (Records(cutover_record=[{"state": "rolling-back"}]), "cutover-rolling-back"),
    (Records(release_record=[{"state": "installing"}]), "release-install-active"),
])
def test_it_refuses_during_a_restore_a_switch_an_abort_or_a_rollback(tmp_path, realm, ledger,
                                                                     reason):
    stage = stage_for(tmp_path, realm, ledger=ledger)
    refused(stage, reason)
    untouched(stage)


@pytest.mark.parametrize("state", ["switching", "rolling-back"])
def test_a_switch_or_cutover_rollback_begun_during_staging_refuses_the_install_at_begin(
        stage, state):
    """The review's fix of 2026-10-26 (the exclusion holds both ways): preflight passed,
    then a switch or a cutover rollback took the live exclusion while the release staged
    and its performance phase ran. `begin` asks again inside its atomic step, so the
    install is refused with that reason before its record exists or v2 is touched."""
    ledger = stage.platform.ledger
    original = stage.platform.performance

    def performance(folder, commit):
        record = rf.cutover_record(ledger, "preparing", releaseTag="v2.0.0")
        path = ("rehearsing", "ready-to-switch", "switching") + (
            ("switched", "rolling-back") if state == "rolling-back" else ())
        for step in path:
            record = rf.advance_cutover(ledger, record, step)
        return original(folder, commit)

    stage.platform.performance = performance
    refused(stage, f"cutover-{state}")
    assert stage.install.records.get(stage.tag) is None
    assert stage.link() == "v2.0.0" and services(stage) == dict.fromkeys(
        ("host", "workers", "scheduler"))


# --- 4. the performance phase's room -------------------------------------------------------------


def test_the_performance_phase_is_refused_below_its_memory_or_load_threshold(stage):
    stage.state["memory"] = 5 * 1024**3
    assert refused(stage, "performance-phase-memory").facts == {"requestRate": 3.0}
    stage.state["memory"], stage.state["rate"] = 16 * 1024**3, 61.0
    assert refused(stage, "performance-phase-load").facts == {"requestRate": 61.0}
    stage.state["rate"] = 12.5
    stage.state["performance"] = {"passed": False}
    breached = refused(stage, "performance-target-breached")
    assert breached.facts == {"requestRate": 12.5}  # production's rate beside the result
    assert stage.link() == "v2.0.0" and stage.install.records.get(stage.tag) is None


# --- 5. a migration that fails in one owner ----------------------------------------------------


def test_a_failed_migration_keeps_the_earlier_owners_and_the_current_release(stage):
    stage.state["migrate"] = {"applied": ["backend/modules/accounts/u8_accounts.sql"],
                              "failed": {"owner": "research", "file": "u8_research.sql"}}
    error = refused(stage, "migration-failed")
    assert error.changed is True and error.facts["failed"]["owner"] == "research"
    assert stage.link() == "v2.0.0"  # the current release keeps running
    assert set(services(stage).values()) == {"running"}
    assert stage.journey.tunnel()["origin"] == "v2-host"
    assert stage.install.records.get(stage.tag)["state"] == "failed"


# --- 6. not ready within 10 minutes switches back by itself ------------------------------------


def test_not_ready_within_ten_minutes_switches_back_and_records_the_time(stage):
    stage.state["ready_on"] = {"v2.0.0"}
    result = stage.install.install(stage.tag)
    assert result["state"] == "switched-back"
    assert stage.link() == "v2.0.0" and stage.link("release-previous") == "v2.0.0"
    record = stage.install.records.get(stage.tag)
    assert record["state"] == "switched-back" and record["readyWaitSeconds"] == 600
    assert result["switchBackSeconds"] >= 0
    assert set(services(stage).values()) == {"running"}
    assert (stage.paths.releases / stage.tag).exists()  # kept for diagnosis


def test_a_failed_probe_journey_switches_back_too(stage):
    stage.state["probe"] = False
    assert stage.install.install(stage.tag)["state"] == "switched-back"
    assert stage.link() == "v2.0.0"


def test_a_switch_back_whose_previous_release_never_becomes_ready_fails_and_keeps_the_notice(
        stage):
    """Review finding (Major, R13): neither release becomes ready. The switch back's own
    wait runs out, so it is a failure (`switch-back-failed` at
    `v2-not-ready-after-switch-back`, `recover` offered) with its wait recorded, and the
    public address stays on the maintenance notice instead of a failing v2. `recover`
    keeps the notice while v2 is still not ready, and routes once it is."""
    stage.state["ready_on"] = set()
    error = refused(stage, "switch-back-failed")
    assert error.facts["step"] == "v2-not-ready-after-switch-back", error.facts
    assert error.facts["offered"] == ["docsuri-release recover"] and error.changed is True
    record = stage.install.records.get(stage.tag)
    assert record["state"] == "switched-back" and record["reasonKey"] == "switch-back-failed"
    assert record["readyWaitSeconds"] == 600 and record["switchBackWaitSeconds"] == 600
    assert stage.link() == "v2.0.0"
    assert stage.journey.tunnel()["origin"] == "maintenance"
    assert stage.install.records.exclusion_blocker() is None
    held = again(stage).recover()
    assert held["routeBack"] == "held" and held["reason"] == "v2-not-ready", held
    assert held["ready"] is False and stage.journey.tunnel()["origin"] == "maintenance"
    assert stage.install.records.get(stage.tag)["reasonKey"] == "route-back-failed"
    stage.state["ready_on"] = {"v2.0.0"}
    result = again(stage).recover()
    assert result["record"] == "switched-back" and result["ready"] is True, result
    assert "routeBack" not in result and stage.journey.tunnel()["origin"] == "v2-host"
    assert set(services(stage).values()) == {"running"}
    assert "reasonKey" not in stage.install.records.get(stage.tag)


# --- 7. the marker is gone and the manifest matches every way out ------------------------------


@pytest.mark.parametrize("way", ["failed-migration", "failed-apply", "switch-back"])
def test_the_marker_is_gone_and_the_manifest_matches_every_way_out(tmp_path, realm, way):
    stage = stage_for(tmp_path, realm, version=2)
    try:
        if way == "failed-migration":
            stage.state["migrate"] = {"failed": {"owner": "accounts"}}
        elif way == "failed-apply":
            stage.state["installer"] = {"failed": "rule-files"}
        else:
            stage.state["ready_on"] = {"v2.0.0"}
        if way == "switch-back":
            assert stage.install.install(stage.tag)["state"] == "switched-back"
        else:
            refused(stage, {"failed-migration": "migration-failed",
                            "failed-apply": "arrangement-apply-failed"}[way])
        assert ("installer", stage.tag) in stage.calls
        assert manifest.marker(stage.paths) is None
        assert manifest.read_manifest(stage.paths).version == 2  # as the installer left it
    finally:
        stage.platform.ledger.close()


def test_a_lower_or_unknown_arrangement_version_is_refused(tmp_path, realm):
    stage = stage_for(tmp_path, realm, version=1)
    try:
        manifest.write_manifest(stage.paths, manifest.Manifest(3), clock=stage.clock)
        refused(stage, "arrangement-version-refused")
        assert not (stage.paths.releases / stage.tag).exists()
    finally:
        stage.platform.ledger.close()


# --- 8. after step 12 only the two linked folders remain -----------------------------------------


def test_after_the_record_only_the_two_linked_folders_remain(stage):
    result = stage.install.install(stage.tag)
    assert result["state"] == "installed" and set(result["removed"]) == {"v1.9.9-junk"}
    assert {path.name for path in stage.paths.releases.iterdir()} == {stage.tag, "v2.0.0"}
    assert stage.link() == stage.tag and stage.link("release-previous") == "v2.0.0"
    record = stage.install.records.get(stage.tag)
    assert record["state"] == "installed" and record["arrangementVersion"] == 1
    assert record["verificationRunRef"] == f"github:{stage.github.commit}"
    assert set(record["stepMilliseconds"]) >= {"preflight", "stage", "performance", "backup",
                                               "migrate", "swap", "start", "route-back"}
    assert stage.journey.tunnel()["origin"] == "v2-host"
    assert set(services(stage).values()) == {"running"}
    pth = next((stage.paths.releases / stage.tag / ".venv").rglob(release.PTH))
    lines = pth.read_text().splitlines()
    assert lines[0] == str((stage.paths.releases / stage.tag).resolve())
    assert lines[1:] == [str(stage.paths.releases / stage.tag / root)
                         for root in release.SOURCE_ROOTS[1:]]
    run_id = result["verification"]["verificationRunId"]
    evidence = stage.paths.control / "releases" / f"verification-run-{run_id}.json"
    recorded = json.loads(evidence.read_bytes())
    assert recorded["conclusion"] == "success" and recorded["passed"] is True
    assert recorded["releaseTag"] == stage.tag and recorded["commit"] == stage.github.commit
    assert evidence.stat().st_mode & 0o777 == 0o644
    # Nothing the release command writes lands in the profile.
    assert not (stage.paths.profile / "evidence" / "releases").exists()
    # The release identity the start's `release` check reads.
    identity = stage.paths.releases / stage.tag / release.RELEASE_IDENTITY
    assert json.loads(identity.read_bytes()) == {"tag": stage.tag,
                                                 "commit": stage.github.commit}
    assert identity.stat().st_mode & 0o777 == 0o644
    # Step 3 ran on the staged release's commit.
    assert ("performance", stage.github.commit) in stage.calls
    # An install holds the live exclusion while it runs; none is left afterwards.
    assert stage.install.records.exclusion_blocker() is None


def test_the_verification_run_moves_the_cutover_record(stage):
    from backend.modules.operations.migration.misfits import Decisions
    from tests.u8_service_operations_integration import cutover_flows as cf

    machine = Cutover(stage.platform.ledger, SYNTHETIC_OPERATIONS, clock=stage.clock)
    machine.begin("v2.0.0")
    run = cf.accepted_dry_run(stage.platform.ledger, now=stage.clock(),
                              decisionsDigest=Decisions.from_ledger(stage.platform.ledger).digest())
    machine.dry_run_accepted(run["runId"])
    result = stage.install.install(stage.tag)
    moved = result["verification"]["cutover"]
    assert moved == {"state": "rehearsing", "soak": "started"}, moved
    record = machine.require()
    assert record["releaseTag"] == stage.tag
    assert record["verificationRunId"] == result["verification"]["verificationRunId"]


def test_verify_after_a_rollback_starts_v2_before_it_starts_the_soak(stage):
    """Your decision of 2026-10-25 ("Follow the design"): after a rollback v2 stayed
    stopped. A verification `verify` passes, with a dry run accepted after the rollback,
    starts v2's three roles and waits for readiness, and only then starts the soak."""
    from backend.modules.operations.migration.misfits import Decisions
    from tests.u8_service_operations_integration import cutover_flows as cf

    stage.install.install(stage.tag)  # no CutoverRecord yet: the install moves nothing
    # As the rollback leaves it: rehearsal mode, admission maintainer-only, v2 stopped.
    stage.journey.set_profile(mode="rehearsal", admission="maintainer-only")
    # The realm's PlatformControl store keeps receipts across runs: each run's keys are
    # its own, so no stop replays an earlier run's receipt.
    attempt = uuid4().hex
    for label in LABELS:
        receipt = stage.platform.operator.execute("platform.service.control", label,
                                                  {"label": label, "action": "stop"},
                                                  key=f"test-rolled-back-stop:{attempt}:{label}")
        assert receipt["outcome"] == "succeeded" and not receipt.get("replayed"), receipt
    assert set(services(stage).values()) == {"stopped"}
    ledger = stage.platform.ledger
    run = cf.accepted_dry_run(ledger, now=stage.clock(),
                              decisionsDigest=Decisions.from_ledger(ledger).digest())
    # A cutover that switched and rolled back, with a dry run accepted after the rollback;
    # the ledger takes each state only by its legal transition.
    record = rf.cutover_record(ledger, "preparing", releaseTag=stage.tag)
    for state in ("rehearsing", "ready-to-switch", "switching", "switched", "rolling-back"):
        record = rf.advance_cutover(ledger, record, state)
    rf.advance_cutover(ledger, record, "rolled-back", acceptedDryRunId=run["runId"])
    verified = stage.install.verify(stage.tag)
    moved = verified["verification"]["cutover"]
    assert moved == {"state": "rehearsing", "soak": "started", "ready": True}, moved
    assert set(services(stage).values()) == {"running"}
    assert "start-rehearsal-v2" in verified["steps"]


def stop_v2(stage) -> None:
    """v2 stopped as a rollback leaves it, under keys of this call's own."""
    attempt = uuid4().hex
    for label in LABELS:
        receipt = stage.platform.operator.execute("platform.service.control", label,
                                                  {"label": label, "action": "stop"},
                                                  key=f"test-rolled-back-stop:{attempt}:{label}")
        assert receipt["outcome"] == "succeeded" and not receipt.get("replayed"), receipt
    assert set(services(stage).values()) == {"stopped"}


def rolled_back(stage, record: dict | None = None) -> dict:
    """The CutoverRecord switched and rolled back, with a dry run accepted after the
    rollback (a new one each time); from rehearsing when `record` is given."""
    from backend.modules.operations.migration.misfits import Decisions
    from tests.u8_service_operations_integration import cutover_flows as cf

    stage.journey.set_profile(mode="rehearsal", admission="maintainer-only")
    stop_v2(stage)
    ledger = stage.platform.ledger
    run = cf.accepted_dry_run(ledger, now=stage.clock(),
                              decisionsDigest=Decisions.from_ledger(ledger).digest())
    if record is None:
        record = rf.cutover_record(ledger, "preparing", releaseTag=stage.tag)
        record = rf.advance_cutover(ledger, record, "rehearsing")
    for state in ("ready-to-switch", "switching", "switched", "rolling-back"):
        record = rf.advance_cutover(ledger, record, state)
    return rf.advance_cutover(ledger, record, "rolled-back", acceptedDryRunId=run["runId"])


class StartFailsOnce:
    """The release's operator, with its first service start failed through U7's injected
    permission fault (a failed receipt bound under the start's key)."""

    def __init__(self, operator):
        self.operator, self.failed = operator, []

    def __getattr__(self, name):
        return getattr(self.operator, name)

    def execute(self, operation, target, inputs, *, key, **options):
        if inputs.get("action") == "start" and not self.failed:
            self.failed.append(key)
            return self.operator.execute(operation, target, inputs, key=key,
                                         injected_fault="permission", **options)
        return self.operator.execute(operation, target, inputs, key=key, **options)


def test_a_failed_start_after_a_rollback_is_retried_by_the_next_verify(stage):
    """The first `verify`'s start fails and starts no soak; the next `verify`, a run of
    its own, starts v2 under its own keys, waits for readiness and starts the soak."""
    stage.install.install(stage.tag)
    rolled_back(stage)
    failing = StartFailsOnce(stage.platform.operator)
    stage.platform.operator = failing
    moved = stage.install.verify(stage.tag)["verification"]["cutover"]
    assert moved["state"] == "rolled-back" and "soak" not in moved, moved
    assert moved["reason"] == "service.control-failed"
    assert stage.install.run_id in failing.failed[0]
    moved = ReleaseInstall(stage.paths, stage.platform, clock=stage.clock).verify(
        stage.tag)["verification"]["cutover"]
    assert moved == {"state": "rehearsing", "soak": "started", "ready": True}, moved
    assert set(services(stage).values()) == {"running"}


def test_a_second_rollback_on_the_same_tag_starts_v2_again(stage):
    """After a second rollback of the same tag, `verify` starts v2 under the new accepted
    dry run's keys: the first rollback's succeeded receipts are never replayed for it."""
    stage.install.install(stage.tag)
    rolled_back(stage)
    assert stage.install.verify(stage.tag)["verification"]["cutover"]["soak"] == "started"
    machine = Cutover(stage.platform.ledger, SYNTHETIC_OPERATIONS, clock=stage.clock)
    rolled_back(stage, machine.require())  # soaked again, switched, rolled back again
    assert set(services(stage).values()) == {"stopped"}
    moved = ReleaseInstall(stage.paths, stage.platform, clock=stage.clock).verify(
        stage.tag)["verification"]["cutover"]
    assert moved == {"state": "rehearsing", "soak": "started", "ready": True}, moved
    assert set(services(stage).values()) == {"running"}


def rolled_back_without_a_dry_run(stage) -> dict:
    """The CutoverRecord switched and rolled back, as the rollback's serving step leaves
    it: rehearsal mode, admission maintainer-only, v2 stopped, no accepted dry run."""
    stage.journey.set_profile(mode="rehearsal", admission="maintainer-only")
    stop_v2(stage)
    ledger = stage.platform.ledger
    record = rf.cutover_record(ledger, "preparing", releaseTag="v2.0.0")
    for state in ("rehearsing", "ready-to-switch", "switching", "switched", "rolling-back"):
        record = rf.advance_cutover(ledger, record, state)
    return rf.advance_cutover(ledger, record, "rolled-back")


def second_tag(stage) -> str:
    """Another annotated tag on `main`, on the same commit, that v2 answers ready on."""
    tag = tag_of()
    stage.github.tags[tag] = dict(stage.github.tags[stage.tag])
    stage.state["ready_on"].add(tag)
    return tag


def test_an_install_after_a_rollback_with_no_dry_run_since_keeps_v2_stopped(stage):
    """Your decision of 2026-10-25 ("Keep v2 stopped"; Step 38 item 6): while the record
    is rolled-back with no dry run accepted since the rollback, the install stages,
    migrates and switches the release and leaves v2's three roles stopped; an install
    after such a dry run starts them, and the soak with them."""
    from backend.modules.operations.migration.misfits import Decisions
    from tests.u8_service_operations_integration import cutover_flows as cf

    rolled_back_without_a_dry_run(stage)
    stage.platform.mode = lambda: "rehearsal"  # as the rollback leaves the profile
    result = stage.install.install(stage.tag)
    assert result["state"] == "installed" and result["v2"] == "stopped", result
    assert stage.link() == stage.tag and stage.link("release-previous") == "v2.0.0"
    assert set(services(stage).values()) == {"stopped"}
    assert "start" not in result["steps"] and "migrate" in result["steps"]
    moved = result["verification"]["cutover"]
    # No soak without a new dry run, and no verification either: the release has not run
    # its probe journey (review finding, Major, R13).
    assert moved == {"state": "rolled-back", "reason": "release-not-probed"}, moved
    machine = Cutover(stage.platform.ledger, SYNTHETIC_OPERATIONS, clock=stage.clock)
    assert "soakStartedAt" not in machine.require()
    assert "verificationRunId" not in machine.require()
    assert machine.require()["releaseTag"] == stage.tag
    # A dry run accepted after the rollback: the next install starts v2, then the soak.
    ledger = stage.platform.ledger
    run = cf.accepted_dry_run(ledger, now=stage.clock(),
                              decisionsDigest=Decisions.from_ledger(ledger).digest())
    machine.dry_run_accepted(run["runId"])
    later = second_tag(stage)
    result = ReleaseInstall(stage.paths, stage.platform, clock=stage.clock).install(later)
    assert result["state"] == "installed" and "v2" not in result, result
    assert "start" in result["steps"]
    assert set(services(stage).values()) == {"running"}
    assert result["verification"]["cutover"] == {"state": "rehearsing", "soak": "started"}


def installed_while_stopped(stage) -> Cutover:
    """A release installed while the record is rolled-back with no dry run accepted
    since, then a dry run accepted after the rollback (so the soak may start)."""
    from backend.modules.operations.migration.misfits import Decisions
    from tests.u8_service_operations_integration import cutover_flows as cf

    rolled_back_without_a_dry_run(stage)
    stage.platform.mode = lambda: "rehearsal"
    result = stage.install.install(stage.tag)
    assert result["state"] == "installed" and result["v2"] == "stopped", result
    machine = Cutover(stage.platform.ledger, SYNTHETIC_OPERATIONS, clock=stage.clock)
    ledger = stage.platform.ledger
    run = cf.accepted_dry_run(ledger, now=stage.clock(),
                              decisionsDigest=Decisions.from_ledger(ledger).digest())
    machine.dry_run_accepted(run["runId"])
    return machine


def test_a_release_installed_while_stopped_is_recorded_as_not_yet_probed(stage):
    """The person's decision of 2026-10-25 ("Probe it when the soak starts"; Step 44 test
    item 7): no probe journey ran at the install, so the record says so, and the cutover's
    soak start waits for it (`unprobed_tag`)."""
    from docsuri_ops.release import unprobed_tag

    machine = installed_while_stopped(stage)
    record = stage.install.records.get(stage.tag)
    assert record["state"] == "installed" and record["probePending"] is True
    assert "probedAt" not in record
    assert unprobed_tag(stage.platform.ledger, stage.paths, clock=stage.clock) == stage.tag
    assert set(services(stage).values()) == {"stopped"}
    # Review finding (Major, R13): the CutoverRecord holds no verification for it, so the
    # only way to one is `verify` once its probe journey passes.
    assert "verificationRunId" not in machine.require()
    assert machine.require()["state"] == "rolled-back"
    # An install that started v2 ran its probe journey: nothing waits.
    assert "probePending" not in (stage.install.records.get("v2.0.0") or {})


def test_at_the_soaks_start_the_release_runs_its_probe_journey(stage):
    from docsuri_ops.release import unprobed_tag

    installed_while_stopped(stage)
    probes = []
    stage.platform.probe = lambda: probes.append(stage.link()) or True
    verified = stage.install.verify(stage.tag)
    moved = verified["verification"]["cutover"]
    assert moved == {"state": "rehearsing", "soak": "started", "ready": True,
                     "probe": "passed"}, moved
    assert probes == [stage.tag]  # the probe journey ran on the installed release
    assert "probe" in verified["steps"] and "start-rehearsal-v2" in verified["steps"]
    record = stage.install.records.get(stage.tag)
    assert record["state"] == "installed" and "probePending" not in record
    assert "probedAt" in record
    assert unprobed_tag(stage.platform.ledger, stage.paths, clock=stage.clock) is None
    assert set(services(stage).values()) == {"running"}


def test_a_release_that_fails_its_probe_at_the_soaks_start_is_switched_back(stage):
    machine = installed_while_stopped(stage)
    stage.state["probe"] = False
    moved = stage.install.verify(stage.tag)["verification"]["cutover"]
    assert moved["state"] == "rolled-back" and "soak" not in moved, moved
    assert moved["probe"] == "failed" and moved["reason"] == "release-probe-failed"
    assert moved["switchedBack"]["state"] == "switched-back"
    # § 6: `release` points back at `release-previous`, the failed folder kept.
    assert stage.link() == "v2.0.0"
    assert (stage.paths.releases / stage.tag).exists()
    assert stage.install.records.get(stage.tag)["state"] == "switched-back"
    record = machine.require()
    # No soak started, and the record names the tag the links point to, whose
    # verification has not passed: no soak on the failed release's verification.
    assert record["state"] == "rolled-back" and "soakStartedAt" not in record
    assert record["releaseTag"] == "v2.0.0" and record.get("verificationRunId") is None
    assert moved["cutoverRelease"] == {"state": "rolled-back", "releaseTag": "v2.0.0"}


def test_a_failed_probe_at_the_soaks_start_leaves_v2_stopped_then_verify_starts_the_soak(
        stage):
    """Your decision of 2026-10-26 ("Leave v2 stopped"; Step 44 test item 1): the switch
    back points `release` at `release-previous` again and leaves v2's three roles stopped,
    each stopped through the service control, so each stop record cites a receipt the
    store holds; the ReleaseRecord ends switched-back with `probePending` cleared; the
    CutoverRecord stays rolled-back, named for the linked tag; `docsuri-release verify`
    on the linked tag then starts the soak."""
    from docsuri_ops.release import unprobed_tag
    from docsuri_ops.u8_platform.u8_protocols import ReceiptReader

    machine = installed_while_stopped(stage)
    stage.state["probe"] = False
    moved = stage.install.verify(stage.tag)["verification"]["cutover"]
    assert moved["probe"] == "failed" and moved["v2"] == "stopped", moved
    assert moved["switchedBack"] == {**moved["switchedBack"], "state": "switched-back",
                                     "v2": "stopped"}
    assert stage.link() == "v2.0.0" and set(services(stage).values()) == {"stopped"}
    operator = stage.platform.operator
    for label in LABELS:
        stop = stage.journey.read_state("stops", f"{label}.json")
        held = operator._read_named(stop["operationId"])
        assert held["operation"] == "platform.service.control"
        assert str(held["targetId"]) == label and ReceiptReader.outcome(held) == "succeeded"
    failed = stage.install.records.get(stage.tag)
    assert failed["state"] == "switched-back" and "probePending" not in failed
    assert unprobed_tag(stage.platform.ledger, stage.paths, clock=stage.clock) is None
    record = machine.require()
    assert record["state"] == "rolled-back" and record["releaseTag"] == "v2.0.0"
    # `cutover check` starts no soak meanwhile: the linked tag's verification has not
    # passed on the record.
    assert record.get("verificationRunId") is None
    # The linked tag's verify starts v2 and the soak.
    release.write_identity(stage.paths.releases / "v2.0.0", "v2.0.0", stage.github.commit,
                           owner_uid=os.getuid())
    stage.github.tags["v2.0.0"] = dict(stage.github.tags[stage.tag])
    stage.state["probe"] = True
    verified = ReleaseInstall(stage.paths, stage.platform, clock=stage.clock).verify("v2.0.0")
    moved = verified["verification"]["cutover"]
    assert moved == {"state": "rehearsing", "soak": "started", "ready": True}, moved
    assert set(services(stage).values()) == {"running"}
    assert machine.require()["releaseTag"] == "v2.0.0"


def test_a_v2_not_ready_at_the_soaks_start_runs_no_probe(stage):
    installed_while_stopped(stage)
    stage.state["ready_on"] = set()
    stage.platform.probe = lambda: pytest.fail("probed a v2 that is not ready")
    moved = stage.install.verify(stage.tag)["verification"]["cutover"]
    assert moved == {"state": "rolled-back", "ready": False, "reason": "v2-not-ready"}, moved
    assert stage.install.records.get(stage.tag)["probePending"] is True


def reached_again_by_a_rollback(stage) -> str:
    """A release installed while v2 was kept stopped (still waiting for its probe), then
    a later release installed once a dry run was accepted (it starts the soak), then
    rolled back with `docsuri-release rollback`: the links point at the release still
    waiting, v2 runs on it, and the CutoverRecord is rehearsing with no soak. Answers the
    later tag."""
    installed_while_stopped(stage)
    later = second_tag(stage)
    result = ReleaseInstall(stage.paths, stage.platform, clock=stage.clock).install(later)
    assert result["state"] == "installed", result
    assert result["verification"]["cutover"]["soak"] == "started", result
    rolled = ReleaseInstall(stage.paths, stage.platform, clock=stage.clock).rollback()
    assert rolled["state"] == "rolled-back" and stage.link() == stage.tag, rolled
    assert stage.install.records.get(stage.tag)["probePending"] is True
    record = Cutover(stage.platform.ledger, SYNTHETIC_OPERATIONS, clock=stage.clock).require()
    assert record["state"] == "rehearsing" and "soakStartedAt" not in record, record
    assert record["releaseTag"] == stage.tag
    return later


def test_a_probe_pending_release_reached_again_by_a_rollback_is_probed_by_verify(stage):
    """Your decision of 2026-10-26, "Probe it whenever it's linked" (Step 44 test item 4):
    `verify` runs the probe journey of the linked release still waiting for it, in a
    state other than rolled-back, and the soak starts only after the probe passed."""
    from docsuri_ops.release import unprobed_tag

    reached_again_by_a_rollback(stage)
    machine = Cutover(stage.platform.ledger, SYNTHETIC_OPERATIONS, clock=stage.clock)
    probes = []

    def probe():
        # The soak has not started when the probe runs.
        assert "soakStartedAt" not in machine.require()
        probes.append(stage.link())
        return True

    stage.platform.probe = probe
    verified = ReleaseInstall(stage.paths, stage.platform, clock=stage.clock).verify(stage.tag)
    moved = verified["verification"]["cutover"]
    assert moved == {"state": "rehearsing", "ready": True, "probe": "passed",
                     "soak": "restarted"}, moved
    assert probes == [stage.tag]
    record = stage.install.records.get(stage.tag)
    assert "probePending" not in record and "probedAt" in record
    assert unprobed_tag(stage.platform.ledger, stage.paths, clock=stage.clock) is None
    assert "soakStartedAt" in machine.require()
    assert set(services(stage).values()) == {"running"}


def test_a_failed_probe_of_a_release_reached_by_a_rollback_stays_put_with_v2_stopped(stage):
    """Your decision of 2026-10-26, "Stay put, v2 stopped" (Step 44 test item 3): the
    probe fails in rehearsing, and the kept release (`release-previous`, the release just
    rolled back from) has a rolled-back record. The switch back never points `release` at
    it: the links stay on the release that failed its probe, v2's three roles stay
    stopped, the record carries `recover-required` and still waits for its probe, so no
    soak starts; `recover` keeps v2 stopped and answers the one way out, a new tag's
    install (your decision of 2026-10-27, "Drop that remedy": no rollback to an earlier
    release, since no earlier release remains under `releases/` after a completed install
    and no link is edited by hand), `rollback` is refused (`kept-release-failed`), and
    the new tag's install from that state succeeds, settling the waiting record."""
    from docsuri_ops.release import RECOVER_REMAINING, unprobed_tag

    assert RECOVER_REMAINING == ("docsuri-release install with a new tag",)
    assert not any("release-previous" in offered for offered in RECOVER_REMAINING)

    later = reached_again_by_a_rollback(stage)
    assert stage.install.records.get(later)["state"] == "rolled-back"
    stage.state["probe"] = False
    moved = ReleaseInstall(stage.paths, stage.platform, clock=stage.clock).verify(
        stage.tag)["verification"]["cutover"]
    assert moved["probe"] == "failed" and moved["reason"] == "release-probe-failed", moved
    assert moved["v2"] == "stopped" and "soak" not in moved
    switched = moved["switchedBack"]
    assert (switched["state"], switched["reason"], switched["step"]) == (
        "failed", "recover-required", "kept-release-closed"), switched
    assert switched["keptRelease"] == later and switched["v2"] == "stopped"
    assert switched["offered"] == RECOVER_REMAINING
    # The links stayed, v2 is stopped through the service control, the record waits.
    assert stage.link() == stage.tag and stage.link("release-previous") == later
    assert set(services(stage).values()) == {"stopped"}
    record = stage.install.records.get(stage.tag)
    assert record["state"] == "installed" and record["probePending"] is True
    assert record["reasonKey"] == "recover-required"
    assert unprobed_tag(stage.platform.ledger, stage.paths, clock=stage.clock) == stage.tag
    machine = Cutover(stage.platform.ledger, SYNTHETIC_OPERATIONS, clock=stage.clock)
    cutover = machine.require()
    assert cutover["releaseTag"] == stage.tag and "soakStartedAt" not in cutover
    # `recover` changes nothing, keeps v2 stopped and answers what remains.
    with pytest.raises(Refused) as caught:
        again(stage).recover()
    error = caught.value
    assert error.reason == "recover-required" and error.changed is False
    assert (error.facts["keptRelease"], error.facts["keptState"]) == (later, "rolled-back")
    assert error.facts["v2"] == "stopped" and error.facts["offered"] == RECOVER_REMAINING
    assert stage.link() == stage.tag and set(services(stage).values()) == {"stopped"}
    assert stage.install.records.get(stage.tag) == record
    # A rollback to the closed kept release is refused as `_rollback_target` holds.
    with pytest.raises(Refused) as refused_rollback:
        again(stage).rollback()
    assert refused_rollback.value.reason == "kept-release-failed"
    assert refused_rollback.value.facts["keptState"] == "rolled-back"
    assert stage.link() == stage.tag
    # No earlier release remains to point `release-previous` at: the later install pruned
    # every folder but the two linked ones, so the one way out is a new tag.
    assert sorted(entry.name for entry in stage.paths.releases.iterdir()
                  if entry.is_dir() and not entry.is_symlink()) == sorted([stage.tag, later])
    # v2 stays stopped until the new tag's install, which succeeds from this state: the
    # waiting record is settled as the plan says (its probe superseded, its reason
    # cleared), the closed kept record is untouched, and `recover` has nothing left.
    assert set(services(stage).values()) == {"stopped"}
    stage.state["probe"] = True
    newer = second_tag(stage)
    stage.platform.sleep(60)
    result = again(stage).install(newer)
    assert result["state"] == "installed", result
    assert stage.link() == newer and stage.link("release-previous") == stage.tag
    settled = stage.install.records.get(stage.tag)
    assert settled["state"] == "installed" and settled["probeSuperseded"] is True
    assert "reasonKey" not in settled and "probePending" not in settled
    assert stage.install.records.get(later)["state"] == "rolled-back"
    assert unprobed_tag(stage.platform.ledger, stage.paths, clock=stage.clock) is None
    # The cutover is rehearsing with a dry run accepted, so the install starts v2 and the
    # soak on the new release (as it is built; a cutover still rolled-back with no dry run
    # accepted would keep v2 stopped and leave the new release waiting for its probe).
    assert set(services(stage).values()) == {"running"}
    with pytest.raises(Refused, match="nothing-to-recover"):
        again(stage).recover()


def test_a_failed_probe_staying_put_whose_stops_fail_says_v2_runs_and_recover_stops_it(
        stage):
    """Review finding (Major, R20): "Stay put, v2 stopped" claimed v2 stopped without
    having stopped it. The kept release is closed and the switch back's stops fail: the
    record and the answer keep the stop's failure as their `step` (the stop's own reason,
    `service.control-failed`) beside `recover-required`, the answer says `v2: running`
    (a role still runs the failed release), and `recover` stops v2's three roles before
    it answers `recover-required`; while the stops keep failing it answers `v2: running`
    too, with `recover` and the operator tool's `service stop` offered."""
    from docsuri_ops.release import RECOVER_REMAINING, RECOVER_STOPS, SERVICE_STOP

    later = reached_again_by_a_rollback(stage)
    stage.state["probe"] = False
    failing = Fails(stage.platform.operator, lambda operation, inputs, n: (
        operation == "platform.service.control" and inputs.get("action") == "stop"))
    stage.platform.operator = failing
    moved = again(stage).verify(stage.tag)["verification"]["cutover"]
    assert moved["probe"] == "failed" and moved["v2"] == "running", moved
    switched = moved["switchedBack"]
    assert (switched["state"], switched["reason"]) == ("failed", "recover-required")
    assert switched["step"] == "service.control-failed" and switched["v2"] == "running"
    assert switched["keptRelease"] == later and switched["offered"] == RECOVER_STOPS
    assert SERVICE_STOP in RECOVER_STOPS and "docsuri-release recover" in RECOVER_STOPS
    assert stage.link() == stage.tag and set(services(stage).values()) == {"running"}
    record = stage.install.records.get(stage.tag)
    assert record["state"] == "installed" and record["probePending"] is True
    assert record["reasonKey"] == "recover-required"
    assert record["switchBackStep"] == "service.control-failed"
    # Error case: `recover` while the stops still fail says so, and v2 still runs.
    with pytest.raises(Refused) as still:
        again(stage).recover()
    assert still.value.reason == "recover-required" and still.value.facts["v2"] == "running"
    assert still.value.facts["step"] == "service.control-failed"
    assert still.value.facts["offered"] == RECOVER_STOPS
    assert set(services(stage).values()) == {"running"}
    # The stops work again: `recover` stops the three roles, then answers what remains.
    stage.platform.operator = failing.operator
    with pytest.raises(Refused) as caught:
        again(stage).recover()
    error = caught.value
    assert error.reason == "recover-required" and error.changed is True
    assert error.facts["v2"] == "stopped" and "step" not in error.facts
    assert (error.facts["keptRelease"], error.facts["keptState"]) == (later, "rolled-back")
    assert error.facts["offered"] == RECOVER_REMAINING
    assert set(services(stage).values()) == {"stopped"} and stage.link() == stage.tag
    assert stage.install.records.get(stage.tag) == record  # the record is left as it is
    # Run again, every role already stopped: nothing changes.
    with pytest.raises(Refused) as settled:
        again(stage).recover()
    assert settled.value.changed is False and settled.value.facts["v2"] == "stopped"
    assert set(services(stage).values()) == {"stopped"}


@pytest.mark.parametrize("killed", [False, True], ids=["interrupted", "killed"])
def test_an_install_interrupted_after_its_start_with_a_closed_kept_release_is_stopped_by_recover(
        stage, monkeypatch, killed):
    """Review finding (Major, R20), the install path: an install interrupted after its
    swap and start (v2 runs on the new release) whose kept release is closed (the base
    release's record rolled-back). `recover` never points the links at the closed
    release; it stops v2's three roles, leaves the public address on the maintenance
    notice, and answers `recover-required` with `v2: stopped`; run again, nothing
    changes.

    The killed variant (review finding, Major, R24): the run was killed outright, so no
    handler ended its record, which stays `installing` and holds the live exclusion.
    `recover` then ends it `failed` with `recover-required` (its step the closed kept
    release), so the exclusion is released and the one way out, a new tag's install, is
    not refused `release-install-active`; the record is otherwise left as it is."""
    records = stage.install.records
    records.begin("v2.0.0", stage.github.commit, previous_tag=None)
    records.finish("v2.0.0", "installed")
    records.finish("v2.0.0", "rolled-back")
    ready = stage.platform.ready

    def interrupted():
        raise KeyboardInterrupt()

    if killed:
        monkeypatch.setattr(ReleaseInstall, "_end_installing", lambda self, tag, reason: None)
    stage.platform.ready = interrupted
    with pytest.raises(KeyboardInterrupt):
        stage.install.install(stage.tag)
    monkeypatch.undo()
    stage.platform.ready = ready
    record = records.get(stage.tag)
    if killed:
        assert record["state"] == "installing" and "reasonKey" not in record
        assert records.exclusion_blocker() == "release-install-active"
    else:
        assert record["state"] == "failed" and record["reasonKey"] == "release-interrupted"
    assert stage.link() == stage.tag and stage.link("release-previous") == "v2.0.0"
    assert set(services(stage).values()) == {"running"}  # started before the interrupt
    with pytest.raises(Refused) as caught:
        again(stage).recover()
    error = caught.value
    assert error.reason == "recover-required" and error.changed is True
    assert (error.facts["keptRelease"], error.facts["keptState"]) == ("v2.0.0", "rolled-back")
    assert error.facts["v2"] == "stopped" and "step" not in error.facts
    assert set(services(stage).values()) == {"stopped"} and stage.link() == stage.tag
    assert stage.journey.tunnel()["origin"] == "maintenance"  # v2 is stopped: no route back
    if killed:
        # The record no longer holds the exclusion: `failed` with `recover-required`.
        ended = records.get(stage.tag)
        assert (ended["state"], ended["reasonKey"]) == ("failed", "recover-required")
        assert ended["switchBackStep"] == "kept-release-closed"
        changed = ("state", "reasonKey", "switchBackStep", "updatedAt")
        assert {key: value for key, value in ended.items() if key not in changed} == {
            key: value for key, value in record.items() if key not in changed}
        assert records.exclusion_blocker() is None
        record = ended
    else:
        assert records.get(stage.tag) == record
    with pytest.raises(Refused) as settled:
        again(stage).recover()
    assert settled.value.changed is False and settled.value.facts["v2"] == "stopped"
    assert records.get(stage.tag) == record
    if killed:
        # The one way out is open: a new tag's install is not refused
        # `release-install-active`; it completes, and `recover` has nothing left.
        newer = second_tag(stage)
        stage.platform.sleep(60)
        result = again(stage).install(newer)
        assert result["state"] == "installed", result
        assert stage.link() == newer and stage.link("release-previous") == stage.tag
        assert "reasonKey" not in records.get(stage.tag)
        with pytest.raises(Refused, match="nothing-to-recover"):
            again(stage).recover()


def switched_back_to_a_superseded_release(stage) -> str:
    """Review finding (Major, R21)'s sequence: rolled-back with no dry run; two releases
    installed while v2 is kept stopped (the first's probe superseded by the second,
    which waits for its own); a dry run accepted; the second fails its probe at the
    soak's start and is switched back to the first, which is linked again with v2 left
    stopped on it. Answers the second tag."""
    from backend.modules.operations.migration.misfits import Decisions
    from tests.u8_service_operations_integration import cutover_flows as cf

    rolled_back_without_a_dry_run(stage)
    stage.platform.mode = lambda: "rehearsal"
    assert stage.install.install(stage.tag)["v2"] == "stopped"
    later = second_tag(stage)
    stage.platform.sleep(60)
    assert again(stage).install(later)["v2"] == "stopped"
    assert stage.install.records.get(stage.tag)["probeSuperseded"] is True
    assert stage.install.records.get(later)["probePending"] is True
    ledger = stage.platform.ledger
    machine = Cutover(ledger, SYNTHETIC_OPERATIONS, clock=stage.clock)
    run = cf.accepted_dry_run(ledger, now=stage.clock(),
                              decisionsDigest=Decisions.from_ledger(ledger).digest())
    machine.dry_run_accepted(run["runId"])
    stage.state["probe"] = False
    moved = again(stage).verify(later)["verification"]["cutover"]
    assert moved["probe"] == "failed" and moved["v2"] == "stopped", moved
    assert moved["switchedBack"]["state"] == "switched-back"
    assert stage.link() == stage.tag and set(services(stage).values()) == {"stopped"}
    marked = stage.install.records.get(later)
    assert marked["state"] == "switched-back" and marked["v2Stopped"] is True
    assert marked["keptTag"] == stage.tag
    return later


def test_a_switch_back_to_a_superseded_release_marks_it_pending_before_any_soak(stage):
    """Review finding (Major, R21): the switch back's relink is the third place `release`
    is pointed at a kept release, and it too marks a superseded kept release as waiting
    for its probe at once; `verify` on it then runs its probe before it spends the
    switch back's mark or starts the soak."""
    from docsuri_ops.release import unprobed_tag

    later = switched_back_to_a_superseded_release(stage)
    waiting = stage.install.records.get(stage.tag)
    assert waiting["probePending"] is True and "probeSuperseded" not in waiting, waiting
    assert unprobed_tag(stage.platform.ledger, stage.paths, clock=stage.clock) == stage.tag
    machine = Cutover(stage.platform.ledger, SYNTHETIC_OPERATIONS, clock=stage.clock)
    probes = []

    def probe():
        assert "soakStartedAt" not in machine.require()  # probed before any soak
        assert stage.install.records.get(later)["v2Stopped"] is True  # the mark unspent
        probes.append(stage.link())
        return True

    stage.platform.probe = probe
    moved = again(stage).verify(stage.tag)["verification"]["cutover"]
    assert moved == {"state": "rehearsing", "soak": "started", "ready": True,
                     "probe": "passed"}, moved
    assert probes == [stage.tag]
    probed = stage.install.records.get(stage.tag)
    assert "probePending" not in probed and "probedAt" in probed
    assert "v2Stopped" not in stage.install.records.get(later)  # the mark is spent
    assert set(services(stage).values()) == {"running"}


def test_a_superseded_release_that_fails_its_own_probe_after_a_switch_back_waits(stage):
    """Review finding (Major, R21), the error case: the kept release the switch back
    linked fails its probe too. After a switch back both links name the kept release
    until the next install, so there is no kept release to switch back to
    (`no-kept-release`): the switch back fails, v2 stays stopped, the record keeps
    waiting for its probe with `switch-back-failed` for `recover`, and no soak starts on
    a release that was never probed.

    The way out (the re-review's Minor of 2026-10-27): `recover` has no link to move
    either, so it keeps v2 stopped, changes nothing and answers `recover-required` with
    `step: no-kept-release` and the one way out, a new tag (`RECOVER_REMAINING`; your
    decision of 2026-10-27, "Drop that remedy"), a second `recover` answers the same, and
    the new tag's install is not refused: it settles the waiting record (its probe
    superseded, its reason cleared) and links `release` at the new tag."""
    from docsuri_ops.release import RECOVER_REMAINING, unprobed_tag

    later = switched_back_to_a_superseded_release(stage)
    assert stage.link("release-previous") == stage.tag  # both links name the kept release
    moved = again(stage).verify(stage.tag)["verification"]["cutover"]  # the probe still fails
    assert moved["probe"] == "failed" and moved["v2"] == "stopped", moved
    switched = moved["switchedBack"]
    assert (switched["reason"], switched["step"]) == ("switch-back-failed", "no-kept-release")
    assert stage.link() == stage.tag and set(services(stage).values()) == {"stopped"}
    record = stage.install.records.get(stage.tag)
    assert record["probePending"] is True and record["reasonKey"] == "switch-back-failed"
    assert record["switchBackStep"] == "no-kept-release"
    assert unprobed_tag(stage.platform.ledger, stage.paths, clock=stage.clock) == stage.tag
    assert stage.install.records.get(later)["state"] == "switched-back"
    machine = Cutover(stage.platform.ledger, SYNTHETIC_OPERATIONS, clock=stage.clock)
    assert "soakStartedAt" not in machine.require()
    # `recover` answers the one way out, keeps v2 stopped and changes nothing: no link
    # moves, the record is as it was, and no soak starts.
    with pytest.raises(Refused) as caught:
        again(stage).recover()
    error = caught.value
    assert error.reason == "recover-required" and error.changed is False, error.facts
    assert error.facts["offered"] == RECOVER_REMAINING
    assert error.facts["v2"] == "stopped" and error.facts["step"] == "no-kept-release"
    assert error.facts["release"] == stage.tag and "keptRelease" not in error.facts
    assert stage.link() == stage.tag and stage.link("release-previous") == stage.tag
    assert set(services(stage).values()) == {"stopped"}
    assert stage.install.records.get(stage.tag) == record
    assert unprobed_tag(stage.platform.ledger, stage.paths, clock=stage.clock) == stage.tag
    assert "soakStartedAt" not in machine.require()
    # Error case: a second `recover` answers the same, and still changes nothing.
    with pytest.raises(Refused) as second:
        again(stage).recover()
    assert second.value.reason == "recover-required" and second.value.changed is False
    assert second.value.facts["offered"] == RECOVER_REMAINING
    assert second.value.facts["v2"] == "stopped" and second.value.facts["step"] == "no-kept-release"
    assert stage.install.records.get(stage.tag) == record
    assert set(services(stage).values()) == {"stopped"}
    # The one way out works: a new tag's install is not refused by the waiting record
    # (`switch-back-failed` on an `installed` record holds no exclusion), it settles that
    # record as a completed install does, links `release` at the new tag and keeps the
    # failed kept release as `release-previous`; the switched-back record is untouched.
    stage.state["probe"] = True
    newer = second_tag(stage)
    stage.platform.sleep(60)
    result = again(stage).install(newer)
    assert result["state"] == "installed", result
    assert stage.link() == newer and stage.link("release-previous") == stage.tag
    settled = stage.install.records.get(stage.tag)
    assert settled["state"] == "installed" and settled["probeSuperseded"] is True
    assert "reasonKey" not in settled and "probePending" not in settled
    assert stage.install.records.get(later)["state"] == "switched-back"
    assert stage.install.records.get(newer)["state"] == "installed"
    assert "probePending" not in stage.install.records.get(newer)
    assert unprobed_tag(stage.platform.ledger, stage.paths, clock=stage.clock) is None
    # The cutover was rolled-back with a dry run accepted, so the install starts v2 and
    # the soak on the new release.
    assert set(services(stage).values()) == {"running"}
    assert "soakStartedAt" in machine.require()
    with pytest.raises(Refused, match="nothing-to-recover"):
        again(stage).recover()


def test_a_new_tag_is_the_other_way_out_after_a_failed_probe_stayed_put(stage):
    """The way out of "Stay put, v2 stopped" (the only one, by your decision of
    2026-10-27, "Drop that remedy"): a new tag's install, which settles the record
    waiting with `recover-required` (its probe superseded, its reason cleared) and runs
    v2 on the new release."""
    later = reached_again_by_a_rollback(stage)
    stage.state["probe"] = False
    moved = ReleaseInstall(stage.paths, stage.platform, clock=stage.clock).verify(
        stage.tag)["verification"]["cutover"]
    assert moved["switchedBack"]["reason"] == "recover-required", moved
    assert set(services(stage).values()) == {"stopped"}
    stage.state["probe"] = True
    newer = second_tag(stage)
    stage.platform.sleep(60)
    result = ReleaseInstall(stage.paths, stage.platform, clock=stage.clock).install(newer)
    assert result["state"] == "installed", result
    assert stage.link() == newer and stage.link("release-previous") == stage.tag
    assert set(services(stage).values()) == {"running"}
    settled = stage.install.records.get(stage.tag)
    assert "reasonKey" not in settled and "probePending" not in settled
    assert settled["probeSuperseded"] is True
    assert stage.install.records.get(later)["state"] == "rolled-back"
    with pytest.raises(Refused, match="nothing-to-recover"):
        again(stage).recover()


def ready_only_when_running(stage) -> None:
    """Readiness as production reads it: v2 answers ready only while its three roles run
    (the fixture's default reads the link alone)."""
    ready = stage.platform.ready
    stage.platform.ready = lambda: set(services(stage).values()) == {"running"} and ready()


def rehearsing_with_a_pending_probe(stage) -> Cutover:
    """A release installed while v2 was kept stopped, then a dry run accepted and the
    cutover moved on to rehearsing (as a soak start on another release leaves it) with
    the installed release still waiting for its probe and v2 stopped: the state in which
    `verify` probes it outside rolled-back."""
    machine = installed_while_stopped(stage)
    record = machine.require()
    rf.advance_cutover(stage.platform.ledger, record, "rehearsing")
    assert machine.require()["state"] == "rehearsing"
    assert "soakStartedAt" not in machine.require()
    assert set(services(stage).values()) == {"stopped"}
    return machine


def test_verify_after_an_in_person_stop_with_nothing_pending_leaves_v2_stopped(stage):
    """Your decision of 2026-10-26, "Only for a pending probe" (Step 44 test item 2): with
    no release waiting for its probe and no failed probe's switch back marked, a `verify`
    in preparing or rehearsing starts nothing. v2 stopped in person stays stopped, the
    answer is `v2-stopped` with the operator tool's `service start` offered, and no
    verification is recorded on the cutover; a v2 that runs gets its soak restarted
    without a start."""
    from docsuri_ops.release import SERVICE_START

    stage.install.install(stage.tag)  # v2 runs on it, probed at the install
    ready_only_when_running(stage)
    ledger = stage.platform.ledger
    rf.cutover_record(ledger, "preparing", releaseTag=stage.tag)
    stop_v2(stage)  # in person, as the operator tool's `service stop` leaves it
    stage.platform.probe = lambda: pytest.fail("probed with nothing pending")
    verified = again(stage).verify(stage.tag)
    moved = verified["verification"]["cutover"]
    assert moved == {"state": "preparing", "reason": "v2-stopped",
                     "offered": [SERVICE_START]}, moved
    assert "start-rehearsal-v2" not in verified["steps"]
    assert set(services(stage).values()) == {"stopped"}
    machine = Cutover(ledger, SYNTHETIC_OPERATIONS, clock=stage.clock)
    assert "verificationRunId" not in machine.require()
    # The same in rehearsing with no soak running: nothing starts, v2 stays stopped.
    rf.advance_cutover(ledger, machine.require(), "rehearsing")
    moved = again(stage).verify(stage.tag)["verification"]["cutover"]
    assert moved == {"state": "rehearsing", "reason": "v2-stopped",
                     "offered": [SERVICE_START]}, moved
    assert set(services(stage).values()) == {"stopped"}
    # Started in person again (the operator tool's `service start`): `verify` starts
    # nothing, records the verification and restarts the soak on the running v2.
    for label in LABELS:
        stage.platform.operator.execute("platform.service.control", label,
                                        {"label": label, "action": "start"},
                                        key=f"test-in-person-start:{uuid4().hex}:{label}")
    assert set(services(stage).values()) == {"running"}
    verified = again(stage).verify(stage.tag)
    assert verified["verification"]["cutover"] == {"state": "rehearsing",
                                                   "soak": "restarted"}
    assert "start-rehearsal-v2" not in verified["steps"]
    assert "soakStartedAt" in machine.require()


def test_verify_with_a_pending_probe_starts_v2_and_probes_outside_rolled_back(stage):
    """Step 44 test item 2: outside rolled-back, a `verify` of the linked release still
    waiting for its probe starts v2's three roles, waits, probes, and then restarts the
    soak; a failed probe is switched back to the base release (whose record is not
    closed), v2 left stopped."""
    from docsuri_ops.release import unprobed_tag

    rehearsing_with_a_pending_probe(stage)
    probes = []
    stage.platform.probe = lambda: probes.append(stage.link()) or True
    verified = again(stage).verify(stage.tag)
    moved = verified["verification"]["cutover"]
    assert moved == {"state": "rehearsing", "ready": True, "probe": "passed",
                     "soak": "restarted"}, moved
    assert probes == [stage.tag] and "start-rehearsal-v2" in verified["steps"]
    assert set(services(stage).values()) == {"running"}
    assert unprobed_tag(stage.platform.ledger, stage.paths, clock=stage.clock) is None


def test_after_a_failed_probes_switch_back_verify_on_the_linked_tag_starts_the_soak(stage):
    """Step 44 test item 2: outside rolled-back, a failed probe's switch back (to a kept
    release whose record is not closed) leaves v2 stopped and marks it on the failed
    release's record (`v2Stopped`, `keptTag`); `verify` on the linked tag then starts v2,
    restarts the soak and clears the mark, so a later `verify` starts nothing again."""
    from docsuri_ops.release import SERVICE_START

    machine = rehearsing_with_a_pending_probe(stage)
    stage.state["probe"] = False
    moved = again(stage).verify(stage.tag)["verification"]["cutover"]
    assert moved["probe"] == "failed" and moved["v2"] == "stopped", moved
    assert moved["switchedBack"]["state"] == "switched-back"
    assert stage.link() == "v2.0.0" and set(services(stage).values()) == {"stopped"}
    failed = stage.install.records.get(stage.tag)
    assert failed["state"] == "switched-back" and "probePending" not in failed
    assert failed["v2Stopped"] is True and failed["keptTag"] == "v2.0.0"
    assert stage.install.records.stopped_on("v2.0.0") == failed
    assert machine.require()["releaseTag"] == "v2.0.0"
    # The linked tag's `verify` starts v2 for the soak, and the mark is spent.
    stage.github.tags["v2.0.0"] = dict(stage.github.tags[stage.tag])
    stage.state["probe"] = True
    verified = again(stage).verify("v2.0.0")
    moved = verified["verification"]["cutover"]
    assert moved == {"state": "rehearsing", "ready": True, "soak": "restarted"}, moved
    assert "start-rehearsal-v2" in verified["steps"]
    assert set(services(stage).values()) == {"running"}
    spent = stage.install.records.get(stage.tag)
    assert "v2Stopped" not in spent and "keptTag" not in spent
    assert stage.install.records.stopped_on("v2.0.0") is None
    # Stopped in person once more: nothing waits, so `verify` starts nothing.
    ready_only_when_running(stage)
    stop_v2(stage)
    record = machine.require()
    rf.advance_cutover(stage.platform.ledger, {k: v for k, v in record.items()
                                               if k != "soakStartedAt"}, "rehearsing")
    moved = again(stage).verify("v2.0.0")["verification"]["cutover"]
    assert moved == {"state": "rehearsing", "reason": "v2-stopped",
                     "offered": [SERVICE_START]}, moved
    assert set(services(stage).values()) == {"stopped"}


def test_an_unprobed_release_while_rolled_back_without_a_dry_run_still_waits(stage):
    """The one state where v2 stays stopped: rolled-back with no dry run accepted. `verify`
    runs no probe and starts nothing there (`release-not-probed`)."""
    rolled_back_without_a_dry_run(stage)
    stage.platform.mode = lambda: "rehearsal"
    assert stage.install.install(stage.tag)["v2"] == "stopped"
    stage.platform.probe = lambda: pytest.fail("probed while v2 is kept stopped")
    moved = ReleaseInstall(stage.paths, stage.platform, clock=stage.clock).verify(
        stage.tag)["verification"]["cutover"]
    assert moved == {"state": "rolled-back", "reason": "release-not-probed"}, moved
    assert set(services(stage).values()) == {"stopped"}


class Receipts:
    """The release's operator, with every receipt it answers kept in order."""

    def __init__(self, operator):
        self.operator, self.receipts = operator, []

    def __getattr__(self, name):
        return getattr(self.operator, name)

    def execute(self, operation, target, inputs, *, key, **options):
        receipt = self.operator.execute(operation, target, inputs, key=key, **options)
        self.receipts.append((operation, key, receipt))
        return receipt


def test_a_second_rollback_of_the_same_tag_acts_again(stage):
    """Step 38 item 7: each release effect's key belongs to its own run. Install, roll
    back, install the same tag again and roll back again, each a command of its own:
    the second rollback's effects all run, none replays the first one's receipts."""
    ReleaseInstall(stage.paths, stage.platform, clock=stage.clock).install(stage.tag)
    log = Receipts(stage.platform.operator)
    stage.platform.operator = log
    first = ReleaseInstall(stage.paths, stage.platform, clock=stage.clock)
    assert first.rollback()["state"] == "rolled-back"
    first_keys = {key for _, key, _ in log.receipts}
    assert stage.link() == "v2.0.0"
    reinstall = ReleaseInstall(stage.paths, stage.platform, clock=stage.clock).install(stage.tag)
    assert reinstall["state"] == "installed" and stage.link() == stage.tag
    log.receipts.clear()
    second = ReleaseInstall(stage.paths, stage.platform, clock=stage.clock)
    result = second.rollback()
    assert result["state"] == "rolled-back" and result["ready"] is True, result
    assert stage.link() == "v2.0.0"
    operations = [operation for operation, _, _ in log.receipts]
    assert operations.count("platform.service.control") == 2 * len(LABELS)
    assert operations.count("platform.tunnel.route") == 2  # live: maintenance, then back
    for _, key, receipt in log.receipts:
        assert receipt["outcome"] == "succeeded" and not receipt.get("replayed"), receipt
        assert second.run_id in key and key not in first_keys
    assert first.run_id != second.run_id
    assert set(services(stage).values()) == {"running"}


def test_no_soak_starts_when_v2_does_not_become_ready_after_a_rollback(stage):
    """v2 started after the rollback but not ready within the 10-minute wait: no soak
    starts on it, and the record stays rolled-back for `cutover check` to start it."""
    stage.install.install(stage.tag)
    rolled_back(stage)
    stage.state["ready_on"] = set()
    moved = stage.install.verify(stage.tag)["verification"]["cutover"]
    assert moved == {"state": "rolled-back", "ready": False, "reason": "v2-not-ready"}, moved
    record = Cutover(stage.platform.ledger, SYNTHETIC_OPERATIONS, clock=stage.clock).require()
    assert "soakStartedAt" not in record and "verificationRunId" in record


def test_a_breached_performance_records_no_passed_run_and_moves_nothing(stage):
    machine = Cutover(stage.platform.ledger, SYNTHETIC_OPERATIONS, clock=stage.clock)
    machine.begin("v2.0.0")
    stage.state["performance"] = {"passed": False}
    refused(stage, "performance-target-breached")
    runs = [json.loads(path.read_bytes())
            for path in (stage.paths.control / "releases").glob("verification-run-*.json")]
    assert len(runs) == 1 and runs[0]["passed"] is False
    assert "verificationRunId" not in machine.require()


def test_verify_runs_only_for_the_installed_tag(stage):
    with pytest.raises(Refused, match="verify-installed-tag-only"):
        stage.install.verify(stage.tag)  # nothing installed yet
    stage.install.install(stage.tag)
    with pytest.raises(Refused, match="verify-installed-tag-only"):
        stage.install.verify("v2.0.0")
    with pytest.raises(Refused, match="tag-outside-its-form"):
        stage.install.verify("main")
    verified = stage.install.verify(stage.tag)
    assert verified["state"] == "verified" and verified["verification"]["passed"] is True
    assert [item for item in stage.calls if item[0] == "performance"] == [
        ("performance", stage.github.commit)] * 2
    code, result = run_program(["verify"], {"tag": stage.tag}, factory=lambda: stage.install)
    assert code == 0 and result["state"] == "verified"


def test_verify_covers_the_release_the_installer_staged(stage):
    """No install record yet: the identity file in the folder `release` points to names
    the tag `verify` takes, and no other."""
    release.write_identity(stage.paths.releases / "v2.0.0", "v2.0.0", "e" * 40,
                           owner_uid=os.getuid())
    with pytest.raises(Refused, match="verify-installed-tag-only"):
        stage.install.verify(stage.tag)
    # Past the gate, the tag's own checks run (this fake GitHub does not know v2.0.0).
    with pytest.raises(Refused, match="tag-unknown"):
        stage.install.verify("v2.0.0")
    assert release.linked_identity(stage.paths) == {"tag": "v2.0.0", "commit": "e" * 40}


# --- step 3 as your login account ----------------------------------------------------------------


class Git:
    """`sudo -n -u <operator> git -C <checkout> …` and the phase itself, recorded."""

    def __init__(self, head: str, *, porcelain: str = "", phase: int = 0):
        self.head, self.porcelain, self.phase, self.argvs = head, porcelain, phase, []

    def __call__(self, argv, **options):
        self.argvs.append((argv, options))
        if "/usr/bin/git" in argv:
            out = self.head + "\n" if "rev-parse" in argv else self.porcelain
            return SimpleNamespace(returncode=0, stdout=out.encode())
        return SimpleNamespace(returncode=self.phase, stdout=b"")


def checkout_pair(tmp_path, *, same_lockfile: bool = True):
    checkout, folder = tmp_path / "checkout", tmp_path / "releases" / "v2.1.0"
    for root in (checkout, folder):
        (root / "frontend").mkdir(parents=True)
    (checkout / ".git").mkdir()
    (folder / release.LOCKFILE).write_text("lock: 1\n")
    (checkout / release.LOCKFILE).write_text("lock: 1\n" if same_lockfile else "lock: 2\n")
    return checkout, folder


def test_step_3_runs_the_release_phase_as_your_login_account(tmp_path):
    from docsuri_ops import production_wiring as wiring

    checkout, folder = checkout_pair(tmp_path)
    commit = "c" * 40
    git = Git(commit)
    inventory = {"inventoryId": "i", "peakRequestsPerSecond": 0.5}
    result = wiring.release_performance(folder, commit, operator="revenant", checkout=checkout,
                                        inventory=inventory, run=git)
    assert result == {"passed": True, "v1Inventory": inventory}
    phase, options = git.argvs[-1]
    assert phase[:5] == ["/usr/bin/sudo", "-n", "-u", "revenant", "/usr/bin/env"]
    assert phase[phase.index("--phase") + 1] == "release-performance"
    assert phase[phase.index("--database") + 1] == "native"
    assert phase[phase.index("--playwright") + 1] == str(checkout)
    assert phase[phase.index("-I") - 1] == str(folder / ".venv" / "bin" / "python")
    assert any(item.startswith(f"{wiring.V1_INVENTORY_ENV}=") for item in phase)
    assert options["env"] == {"PATH": "/usr/bin:/bin"} and options["cwd"] == folder
    assert all(argv[:4] == ["/usr/bin/sudo", "-n", "-u", "revenant"] for argv, _ in git.argvs)
    failing = Git(commit, phase=1)
    assert wiring.release_performance(folder, commit, operator="revenant", checkout=checkout,
                                      inventory=None, run=failing)["passed"] is False
    assert not any("=" in item and item.split("=")[0].isupper()
                   for item in failing.argvs[-1][0])


@pytest.mark.parametrize(("change", "reason"), [
    ({"head": "d" * 40}, "playwright-checkout-commit-differs"),
    ({"porcelain": " M frontend/x.ts\n"}, "playwright-checkout-not-clean"),
    ({"lockfile": False}, "playwright-lockfile-differs"),
    ({"git": False}, "playwright-checkout-missing"),
])
def test_step_3_refuses_a_checkout_that_does_not_measure_the_release(tmp_path, change, reason):
    from docsuri_ops import production_wiring as wiring

    checkout, folder = checkout_pair(tmp_path, same_lockfile=change.get("lockfile", True))
    if change.get("git") is False:
        (checkout / ".git").rmdir()
    git = Git(change.get("head", "c" * 40), porcelain=change.get("porcelain", ""))
    with pytest.raises(Refused, match=reason):
        wiring.release_performance(folder, "c" * 40, operator="revenant", checkout=checkout,
                                   inventory=None, run=git)
    assert not any("--phase" in argv for argv, _ in git.argvs)  # the phase never ran


def test_the_operators_checkout_is_named_by_the_installation(tmp_path):
    from docsuri_ops import production_wiring as wiring

    paths = ArrangementPaths.under(tmp_path / "Library" / "DocSuri")
    paths.control.mkdir(parents=True)
    with pytest.raises(wiring.WiringRefused, match="operator-checkout-unconfigured"):
        wiring.operator_checkout(paths)
    (paths.control / "installation.json").write_text(json.dumps(
        {"operatorCheckout": str(tmp_path / "checkout")}))
    assert wiring.operator_checkout(paths) == tmp_path / "checkout"


def test_a_rollback_switches_back_to_the_kept_release(stage):
    stage.install.install(stage.tag)
    result = stage.install.rollback()
    assert result["state"] == "rolled-back" and result["release"] == "v2.0.0"
    assert stage.link() == "v2.0.0" and stage.link("release-previous") == stage.tag
    assert stage.install.records.get(stage.tag)["state"] == "rolled-back"


# --- a release rollback and the cutover ---------------------------------------------------------


@pytest.mark.parametrize("ledger,reason", [
    (Records(recovery_request=[{"operation": "restore.production", "environment": "live",
                                "state": "running"}]), "production-restore-active"),
    (Records(cutover_record=[{"state": "switching"}]), "cutover-switching"),
    (Records(cutover_record=[{"state": "aborting"}]), "cutover-aborting"),
    (Records(cutover_record=[{"state": "rolling-back"}]), "cutover-rolling-back"),
    (Records(release_record=[{"state": "installing"}]), "release-install-active"),
    (Records(release_record=[{"state": "rolling-back"}]), "release-rollback-active"),
])
def test_a_rollback_is_refused_while_anything_holds_the_live_exclusion(tmp_path, realm, ledger,
                                                                      reason):
    """`docsuri-release rollback` takes the same exclusion as an install: during a
    production restore, a cutover's switch, abort or rollback, an install or another
    release rollback it is refused, and nothing moves."""
    stage = stage_for(tmp_path, realm, ledger=ledger)
    os.symlink(stage.paths.releases / "v1.9.9-junk", stage.paths.release_previous)
    with pytest.raises(Refused) as raised:
        stage.install.rollback()
    assert raised.value.reason == reason and raised.value.changed is False
    assert stage.link() == "v2.0.0" and stage.journey.tunnel() is None
    assert services(stage) == dict.fromkeys(("host", "workers", "scheduler"))


class Watching:
    """The release's operator, noting at each effect what holds the live exclusion."""

    def __init__(self, operator, records):
        self.operator, self.records, self.seen = operator, records, []

    def __getattr__(self, name):
        return getattr(self.operator, name)

    def execute(self, operation, target, inputs, *, key):
        self.seen.append((operation, inputs.get("action"), self.records.exclusion_blocker()))
        return self.operator.execute(operation, target, inputs, key=key)


def test_a_rollback_holds_the_live_exclusion_while_it_runs(stage):
    """While the links switch back, the ReleaseRecord is rolling-back: no backup,
    restore, disposal or install starts beside it; once it ends, nothing is held."""
    from backend.modules.operations.recovery import RecoveryRequests

    stage.install.install(stage.tag)
    watching = Watching(stage.platform.operator, stage.install.records)
    stage.platform.operator = watching
    result = stage.install.rollback()
    assert result["state"] == "rolled-back" and result["ready"] is True, result
    assert watching.seen and all(blocker == "release-rollback-active"
                                 for _, _, blocker in watching.seen), watching.seen
    assert stage.install.records.exclusion_blocker() is None
    requests = RecoveryRequests(stage.platform.ledger, SYNTHETIC_OPERATIONS, clock=stage.clock)
    request = requests.request(origin="schedule", operation="backup.create",
                               environment="live", target_id="docsuri_u8",
                               expected_revision=0, submission_id=uuid4())
    assert requests.admit(request["recoveryRequestId"])["state"] == "awaiting-operator"


def test_a_failed_rollback_releases_the_exclusion(stage):
    """A rollback that stops before the links switch (v2's stop failed) is refused and
    leaves the release installed: the exclusion it held is released."""
    stage.install.install(stage.tag)
    failing = StopFails(stage.platform.operator)
    stage.platform.operator = failing
    with pytest.raises(Refused) as raised:
        stage.install.rollback()
    assert raised.value.changed is True, raised.value
    assert stage.link() == stage.tag
    record = stage.install.records.get(stage.tag)
    assert record["state"] == "installed" and record["reasonKey"] == "release-rollback-failed"
    assert stage.install.records.exclusion_blocker() is None
    # The release as it was: v2 running, the public address routed back to it.
    assert set(services(stage).values()) == {"running"}
    assert stage.journey.tunnel()["origin"] == "v2-host"
    assert stage.install.records.installed()["releaseTag"] == stage.tag


class StopFails:
    """The release's operator, with every service stop failed through U7's injected
    permission fault."""

    def __init__(self, operator):
        self.operator = operator

    def __getattr__(self, name):
        return getattr(self.operator, name)

    def execute(self, operation, target, inputs, *, key):
        if inputs.get("action") == "stop":
            return self.operator.execute(operation, target, inputs, key=key,
                                         injected_fault="permission")
        return self.operator.execute(operation, target, inputs, key=key)


def test_a_rollback_after_a_cutover_rollback_keeps_v2_stopped_and_names_the_tag(stage):
    """While the CutoverRecord is rolled-back with no dry run accepted since (your
    decision of 2026-10-25, "Keep v2 stopped"), `docsuri-release rollback` switches the
    links back and leaves v2's three roles stopped; the record then names the tag the
    links point to."""
    stage.install.install(stage.tag)
    stage.journey.set_profile(mode="rehearsal", admission="maintainer-only")
    stop_v2(stage)
    ledger = stage.platform.ledger
    record = rf.cutover_record(ledger, "preparing", releaseTag=stage.tag)
    for state in ("rehearsing", "ready-to-switch", "switching", "switched", "rolling-back"):
        record = rf.advance_cutover(ledger, record, state)
    rf.advance_cutover(ledger, record, "rolled-back")
    stage.platform.mode = lambda: "rehearsal"  # as the cutover's rollback leaves it
    result = stage.install.rollback()
    assert result["state"] == "rolled-back" and result["v2"] == "stopped", result
    assert stage.link() == "v2.0.0" and stage.link("release-previous") == stage.tag
    assert set(services(stage).values()) == {"stopped"}
    assert result["cutover"] == {"state": "rolled-back", "releaseTag": "v2.0.0"}, result
    machine = Cutover(ledger, SYNTHETIC_OPERATIONS, clock=stage.clock)
    assert machine.require()["releaseTag"] == "v2.0.0"
    assert stage.install.records.get(stage.tag)["state"] == "rolled-back"


@pytest.mark.parametrize("v2_before", ["stopped", "started-not-ready"])
def test_a_rollback_while_rolled_back_with_an_accepted_dry_run_and_no_soak_keeps_v2_stopped(
        stage, v2_before):
    """The review's fix of 2026-10-26: while the CutoverRecord is rolled-back, v2 starts
    only with the soak's start, so a `docsuri-release rollback` with a dry run accepted
    since the rollback but no soak started (its verification not passed yet, or v2 not
    ready at the soak's start, `cutover check` to run again) also leaves v2's three roles
    stopped. The record's earlier `soakStartedAt`, from before the switch, does not
    count as a soak."""
    stage.install.install(stage.tag)
    rolled_back(stage)
    machine = Cutover(stage.platform.ledger, SYNTHETIC_OPERATIONS, clock=stage.clock)
    assert machine.require()["state"] == "rolled-back"
    if v2_before == "started-not-ready":
        stage.state["ready_on"] = set()
        moved = stage.install.verify(stage.tag)["verification"]["cutover"]
        assert moved["reason"] == "v2-not-ready" and set(services(stage).values()) == {
            "running"}
        stage.state["ready_on"] = {stage.tag, "v2.0.0"}
    stage.platform.mode = lambda: "rehearsal"
    result = again(stage).rollback()
    assert result["state"] == "rolled-back" and result["v2"] == "stopped", result
    assert stage.link() == "v2.0.0" and set(services(stage).values()) == {"stopped"}
    assert machine.require()["state"] == "rolled-back"


# --- the pre-release backup through the realm's recovery procedures -----------------------------


@dataclasses.dataclass
class Backed:
    stage: Stage
    database: rf.JourneyDatabase
    rehearsal: str
    procedures: object


class BackupFails:
    """The procedures' operator, with its first `platform.database.backup` failed
    through U7's injected permission fault (a failed receipt bound under its key)."""

    def __init__(self, operator):
        self.operator, self.failed = operator, []

    def __getattr__(self, name):
        return getattr(self.operator, name)

    def execute(self, operation, target, inputs, *, key):
        if operation == "platform.database.backup" and not self.failed:
            self.failed.append(key)
            return self.operator.execute(operation, target, inputs, key=key,
                                         injected_fault="permission")
        return self.operator.execute(operation, target, inputs, key=key)


@pytest.fixture
def backed(tmp_path, realm):
    """A stage whose backup after writes stop is production's own closure
    (`production_wiring.release_backup`) over the realm's RecoveryProcedures and agent,
    on a journey database of the test's own (its production stand-in and a rehearsal
    database), with the agent's stand-in volume: each set is a real one."""
    from psycopg import sql

    from docsuri_ops import production_wiring as wiring
    from docsuri_ops.u8_platform.recovery_words import realm_procedures
    from tests.u8_service_operations_integration.component.test_disposal_pass import (
        disposable,
    )

    database = rf.JourneyDatabase(realm).create()
    rehearsal = disposable(realm, "rehearsal", database.names)
    with rf.admin(realm) as conn:
        conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO docsuri_backup_agent").format(
            sql.Identifier(rehearsal)))
    with rf.admin(realm, rehearsal) as conn:
        conn.execute("CREATE TABLE rehearsal_rows(id int PRIMARY KEY)")
        conn.execute("INSERT INTO rehearsal_rows VALUES (1)")
    stage = None
    try:
        agent = rf.journey_agent(tmp_path, realm, database, lambda: af.NOW)
        stage = stage_for(tmp_path, realm, rehearsal=rehearsal, agentFolder=str(agent))
        procedures = realm_procedures(stage.journey.profile, stage.platform.ledger,
                                      clock=stage.clock, ready=lambda: True,
                                      names=database.names).procedures
        backup = wiring.release_backup(procedures, lambda: stage.platform.mode())
        stage.platform.backup = backup
        stage.platform.backup_plan, stage.platform.backup_settle = backup.plan, backup.settle
        yield Backed(stage, database, rehearsal, procedures)
    finally:
        if stage is not None:
            stage.platform.ledger.close()
        rf.drop_database(realm, rehearsal)
        database.drop()


def sets(stage, environment: str) -> list[dict]:
    return [item for item in stage.platform.ledger.records("backup-set")
            if item["environment"] == environment]


def test_a_failed_pre_release_backup_starts_v2_again_and_frees_the_exclusion(backed):
    """The pre-release backup fails inside the recovery procedures (`ProcedureFailed`):
    the install ends its record `failed`, v2 is started again and the public address
    routed back, the next live backup is admitted, and the next install, a run of its
    own, takes the set again and installs."""
    from backend.modules.operations.recovery import RecoveryRequests

    stage = backed.stage
    failing = BackupFails(backed.procedures.platform.operator)
    backed.procedures.platform.operator = failing
    error = refused(stage, "pre-release-backup-failed")
    assert error.changed is True and error.facts["cause"] == "backup-failed", error.facts
    assert set(services(stage).values()) == {"running"}
    assert stage.journey.tunnel()["origin"] == "v2-host"
    assert stage.link() == "v2.0.0"
    assert stage.install.records.get(stage.tag)["state"] == "failed"
    assert stage.install.records.exclusion_blocker() is None
    assert sets(stage, "live") == []  # a failed set is not recorded
    requests = RecoveryRequests(stage.platform.ledger, SYNTHETIC_OPERATIONS, clock=stage.clock)
    request = requests.request(origin="schedule", operation="backup.create",
                               environment="live", target_id=backed.database.name,
                               expected_revision=0, submission_id=uuid4())
    assert requests.admit(request["recoveryRequestId"])["state"] == "awaiting-operator"
    # The next install is a run of its own: its set's key is new, so the failed receipt
    # is not replayed, and the set is taken.
    result = ReleaseInstall(stage.paths, stage.platform, clock=stage.clock).install(stage.tag)
    assert result["state"] == "installed", result
    (taken,) = sets(stage, "live")
    assert taken["integrity"] == "passed" and taken["backupId"] == stage.install.records.get(
        stage.tag)["backupId"]
    assert taken["databaseIncarnation"].startswith(f"{backed.database.name}:")
    assert len(failing.failed) == 1 and stage.tag in failing.failed[0]


def backup_entries(stage) -> list[dict]:
    path = stage.paths.control / "releases" / release.EFFECT_JOURNAL
    entries = json.loads(path.read_bytes())["entries"] if path.exists() else []
    return [entry for entry in entries if entry.get("kind") == "backup"]


def test_the_in_person_ledger_copy_lies_beside_the_pre_release_set(backed, tmp_path):
    """Production's in-person ledger copy (role `operator`, the release platform's own):
    the install takes its set with a LedgerCopy beside it (review finding, Critical,
    R15)."""
    stage = backed.stage
    copies = rf.InPersonCopy(backed.procedures, stage.platform.ledger, tmp_path)
    result = stage.install.install(stage.tag)
    assert result["state"] == "installed", result
    (taken,) = sets(stage, "live")
    (copy,) = stage.platform.ledger.records("ledger-copy")
    assert copy["backupId"] == taken["backupId"] and copy.get("verifiedAt")
    assert copies.vias == ["in-person"]
    assert [entry["state"] for entry in backup_entries(stage)] == ["settled"]


def through_driver(answers: list, **options):
    """Production's arrangement driver for the operator's effects, run as root (the release
    command), with your login named in its configuration and a stand-in for `sudo`."""
    from docsuri_ops.u8_platform.drivers.arrangement import ArrangementDriver

    config = {"kind": "arrangement", "production": True, "actor": "operator",
              "databasePort": 15432, "v1Stores": {}, **options.pop("config", {})}
    calls = []

    def run(argv, *, input, capture_output, timeout, check):
        calls.append(argv)
        answer = json.dumps(answers.pop(0)).encode() + b"\n"
        return SimpleNamespace(returncode=0, stdout=answer, stderr=answer)

    # The root-owned authority identities, the one source of your login for a root driver
    # (review finding, Minor, R17).
    authorities = options.pop("authorities", lambda: {"actors": {"operator": "maintainer"}})
    return ArrangementDriver(config, run=run, euid=options.pop("euid", lambda: 0),
                             authorities=authorities, **options), calls


def test_the_release_reaches_the_agents_backup_and_ledger_copy_through_your_login(
        backed, tmp_path, clock):
    """Your decision of 2026-10-26, "Through your login": the release command runs as
    root, so its backup after writes stop and its ledger copy reach the agent through
    your login's own in-person grant, `sudo -u <you> /usr/bin/sudo -k -u
    _docsuri_r1t_backup <agent> backup|ledger-copy`; every other word keeps its own
    invocation; root without your login named, or a service account named as you, is
    refused before anything runs; and the agent still refuses root."""
    from docsuri_ops.u8_platform.drivers import DriverRefused
    from docsuri_ops.u8_platform.drivers.arrangement import SUDO
    from tests.u8_service_operations_integration import agent_flows

    agent = "/Library/DocSuri/release/ops/bin/docsuri-backup-agent"
    record = str(uuid4())
    answers = [{"ok": True, "location": "archives/live-set-x.archive", "recordId": record,
                "sha256": "a" * 64, "size": 1},
               {"ok": True, "recordId": str(uuid4()), "location": "u8/ledger-copy-x"}]
    driver, calls = through_driver(answers, config={"operatorLogin": "maintainer"})
    refs = driver.effect("database-backup", {"database": "docsuri_v2", "recordId": record,
                                             "via": "in-person"},
                         context={"operationId": str(uuid4())})
    assert refs[0] == "backup-volume/archives/live-set-x.archive"
    driver.ledger_copy(b"ledger bytes", via="in-person")
    assert calls == [
        [SUDO, "-u", "maintainer", SUDO, "-k", "-u", "_docsuri_r1t_backup", agent, "backup"],
        [SUDO, "-u", "maintainer", SUDO, "-k", "-u", "_docsuri_r1t_backup", agent,
         "ledger-copy"],
    ]
    # Every other word, and the standing set, keep their own invocation.
    assert driver.command("_docsuri_r1t_backup", "docsuri-backup-agent", "stream-back",
                          via="in-person")[:2] == [SUDO, "-k"]
    assert driver.command("_docsuri_r1t_backup", "docsuri-backup-agent", "backup",
                          via="standing")[:2] == [SUDO, "-n"]
    assert driver.command("_docsuri_v2", "docsuri-ledger", "copy",
                          via="in-person")[:2] == [SUDO, "-k"]
    # Not root (your own login account): unchanged, the agent sees you directly.
    plain, _ = through_driver([], euid=lambda: 501, config={"operatorLogin": "maintainer"})
    assert plain.command("_docsuri_r1t_backup", "docsuri-backup-agent", "backup",
                         via="in-person")[:2] == [SUDO, "-k"]
    # Root takes your login from the root-owned authority identities, so a configuration
    # that names no login still reaches the agent through you (review finding, Minor,
    # R17), and root with no identities recorded is refused before anything runs.
    from_file, from_file_calls = through_driver([answers[1]] if answers else [
        {"ok": True, "recordId": str(uuid4()), "location": "u8/ledger-copy-y"}])
    from_file.ledger_copy(b"x", via="in-person")
    assert from_file_calls[0][:3] == [SUDO, "-u", "maintainer"]
    unnamed, unnamed_calls = through_driver([], authorities=lambda: None)
    with pytest.raises(DriverRefused, match="through-login-unconfigured"):
        unnamed.ledger_copy(b"x", via="in-person")
    assert unnamed_calls == []
    # A configured login that differs from the recorded one is refused: `driver.json` is
    # your login's own file, the identities are root's. So is any service account named
    # as you, the scheduler's included, in the file or in the configuration.
    with pytest.raises(DriverRefused, match="through-login-refused"):
        through_driver([], config={"operatorLogin": "someone-else"})
    for name in ("root", "_docsuri_v2", "_docsuri_r1t_backup", "_docsuri_v2_sched",
                 "Bad Name", 7):
        with pytest.raises(DriverRefused, match="through-login-refused"):
            through_driver([], config={"operatorLogin": name},
                           authorities=lambda name=name: {"actors": {"operator": name}})
        with pytest.raises(DriverRefused, match="through-login-refused"):
            through_driver([], authorities=lambda name=name: {"actors": {"operator": name}})
    with pytest.raises(DriverRefused, match="through-login-refused"):
        through_driver([], config={"operatorLogin": "_docsuri_v2_sched"})
    # Not root: the identities are not read, and the configuration is not trusted either.
    assert through_driver([], euid=lambda: 501, authorities=lambda: None,
                          config={"operatorLogin": "_docsuri_v2_sched"})[0]._through is None
    # The installation names your login in the operator's driver configuration only.
    from docsuri_ops.arrangement import installer

    ctx = SimpleNamespace(v1_stores={}, v1_sources={}, v1_checkout=None, operator="maintainer",
                          paths=SimpleNamespace(scheduler_credentials=tmp_path / "c.json"))
    assert installer.driver_config(ctx, "operator")["operatorLogin"] == "maintainer"
    assert "operatorLogin" not in installer.driver_config(ctx, "scheduler")
    # The agent's caller rule is unchanged: root is refused its backup and ledger copy.
    rig = agent_flows.build(tmp_path / "agent", clock)
    for word in ("backup", "ledger-copy"):
        status, result, _ = agent_flows.invoke(rig, word, {}, caller=0)
        assert (status, result["reason"]) == (2, "caller-refused")
    # And an install through the release platform records its pre-release set.
    stage = backed.stage
    assert stage.install.install(stage.tag)["state"] == "installed"
    (taken,) = sets(stage, "live")
    assert taken["trigger"] == "pre-release" and taken["integrity"] == "passed"


def test_a_ledger_copy_that_keeps_failing_settles_and_never_wedges_later_commands(backed,
                                                                                  tmp_path):
    """The set applied and was recorded, but its ledger copy was refused: the install's
    way out runs (`ledger-copy-failed`) and its backup entry stays pending for its
    receipt. The next command settles it by that receipt; the copy is refused again, so
    the entry settles with its failure recorded instead of refusing that command and
    every later one, and the install takes its own set and installs; a rollback follows."""
    stage = backed.stage
    rf.InPersonCopy(backed.procedures, stage.platform.ledger, tmp_path, failures=2)
    error = refused(stage, "pre-release-backup-failed")
    assert error.facts["cause"] == "ledger-copy-failed", error.facts
    (first,) = sets(stage, "live")
    assert first["integrity"] == "passed"  # recorded, without its copy
    assert stage.platform.ledger.records("ledger-copy") == []
    assert [entry["state"] for entry in backup_entries(stage)] == ["pending"]
    result = ReleaseInstall(stage.paths, stage.platform, clock=stage.clock).install(stage.tag)
    assert result["state"] == "installed", result
    earlier, own = backup_entries(stage)
    assert earlier["state"] == "settled" and earlier["failure"] == "ledger-copy-failed"
    assert own["state"] == "settled" and "failure" not in own
    live = sets(stage, "live")
    assert len(live) == 2 and live[0]["backupId"] == first["backupId"]
    (copy,) = stage.platform.ledger.records("ledger-copy")
    assert copy["backupId"] == live[1]["backupId"]
    rolled = ReleaseInstall(stage.paths, stage.platform, clock=stage.clock).rollback()
    assert rolled["state"] == "rolled-back", rolled


def test_a_reinstall_takes_a_new_set_and_a_mode_change_backs_up_that_modes_database(backed):
    """Each install's set is its own: install, roll back and install the same tag again,
    and the second install takes a new set of production's database, not the first
    one's; after the profile moves to rehearsal, the next reinstall backs up the
    rehearsal database (a fixed key would have replayed the first set, or been refused
    for its changed input)."""
    stage = backed.stage
    first = ReleaseInstall(stage.paths, stage.platform, clock=stage.clock).install(stage.tag)
    assert first["state"] == "installed", first
    assert ReleaseInstall(stage.paths, stage.platform, clock=stage.clock).rollback()[
        "state"] == "rolled-back"
    again = ReleaseInstall(stage.paths, stage.platform, clock=stage.clock).install(stage.tag)
    assert again["state"] == "installed", again
    live = sets(stage, "live")
    assert len(live) == 2 and live[0]["backupId"] != live[1]["backupId"], live
    assert all(item["integrity"] == "passed" and item["databaseIncarnation"].startswith(
        f"{backed.database.name}:") for item in live)
    assert stage.install.records.get(stage.tag)["backupId"] == live[1]["backupId"]
    assert ReleaseInstall(stage.paths, stage.platform, clock=stage.clock).rollback()[
        "state"] == "rolled-back"
    stage.journey.set_profile(mode="rehearsal", admission="maintainer-only")
    stage.platform.mode = lambda: "rehearsal"
    third = ReleaseInstall(stage.paths, stage.platform, clock=stage.clock).install(stage.tag)
    assert third["state"] == "installed", third
    (rehearsal,) = sets(stage, "rehearsal")
    assert rehearsal["integrity"] == "passed"
    assert rehearsal["databaseIncarnation"].startswith(f"{backed.rehearsal}:"), rehearsal
    assert stage.install.records.get(stage.tag)["backupId"] == rehearsal["backupId"]
    assert len(sets(stage, "live")) == 2


def test_an_unknown_backup_outcome_is_the_installs_way_out_too(stage):
    """A pre-release backup whose outcome stays unknown (`OutcomeUnknown`) is handled as
    a failed one: v2 starts again, the address routes back, the record ends failed."""
    from backend.modules.operations.recovery_procedures import OutcomeUnknown

    keys: list[str] = []

    def unknown(tag: str, key: str) -> dict:
        keys.append(key)
        raise OutcomeUnknown(str(uuid4()))

    stage.platform.backup = unknown
    error = refused(stage, "pre-release-backup-failed")
    assert error.facts["cause"] == "effect-outcome-unknown", error.facts
    assert set(services(stage).values()) == {"running"}
    assert stage.journey.tunnel()["origin"] == "v2-host"
    assert stage.install.records.get(stage.tag)["state"] == "failed"
    assert stage.install.records.exclusion_blocker() is None
    assert keys and stage.install.run_id in keys[0] and stage.tag in keys[0]


def test_any_other_failure_after_the_record_began_ends_it(stage):
    """A step that fails with anything but a refusal (here the migration raising) still
    ends the ReleaseRecord, so the live exclusion is never left held; before the swap v2
    is started again and the address routed back."""

    def broken(folder: Path) -> dict:
        raise RuntimeError("unexpected")

    stage.platform.migrate = broken
    error = refused(stage, "release-step-failed")
    assert error.changed is True and error.facts == {"cause": "RuntimeError"}, error.facts
    record = stage.install.records.get(stage.tag)
    assert record["state"] == "failed" and record["reasonKey"] == "release-step-failed"
    assert stage.install.records.exclusion_blocker() is None
    assert set(services(stage).values()) == {"running"}
    assert stage.journey.tunnel()["origin"] == "v2-host" and stage.link() == "v2.0.0"
    code, result = run_program(["install"], {"tag": stage.tag}, factory=lambda: stage.install)
    assert (code, result["reason"]) == (1, "release-step-failed")


# --- the program and the release environment ----------------------------------------------------


def run_program(argv, document=None, environ=None, factory=None):
    stdout = io.BytesIO()
    payload = b"" if document is None else json.dumps(document).encode()
    code = release.run(argv, stdin=io.BytesIO(payload), stdout=stdout,
                       environ=environ or {}, factory=factory or (lambda: None))
    return code, json.loads(stdout.getvalue())


def test_the_program_takes_one_word_and_the_tag_on_standard_input(stage):
    assert run_program(["deploy"]) == (2, {"ok": False, "reason": "word-refused"})
    assert run_program(["install"], environ={"PYTHONPATH": "/x"})[1]["reason"] == (
        "environment-refused")
    assert run_program(["install"], {"tag": "v2.0.0", "x": 1})[1]["reason"] == "input-refused"
    assert run_program(["rollback"], {"tag": "v2.0.0"})[1]["reason"] == "input-refused"
    code, result = run_program(["install"], {"tag": stage.tag}, factory=lambda: stage.install)
    assert code == 0 and result["state"] == "installed"
    code, result = run_program(["install"], {"tag": "v9.9.9"}, factory=lambda: stage.install)
    assert (code, result["reason"], result["changed"]) == (1, "tag-unknown", False)


def test_the_release_environment_leaves_out_the_local_packages(tmp_path):
    folder = tmp_path / "releases" / "v2.0.0"
    argv = release.sync_command(Path("/Library/DocSuri/runtimes/uv-0.9.0/uv"), folder)
    assert argv[:6] == ["/Library/DocSuri/runtimes/uv-0.9.0/uv", "sync", "--project",
                        str(folder / "backend"), "--frozen", "--no-build"]
    left_out = [argv[index + 1] for index, item in enumerate(argv)
                if item == "--no-install-package"]
    assert left_out == list(release.LOCAL_PACKAGES)
    environment = release.sync_environment(folder, uv=Path("/x/uv"))
    assert environment["UV_PROJECT_ENVIRONMENT"] == str(folder / ".venv")
    assert environment["UV_PYTHON_INSTALL_DIR"] == str(folder / ".python")
    assert environment["HOME"] == str(folder) and "PYTHONPATH" not in environment
    with pytest.raises(Refused, match="site-packages"):
        release.site_packages(folder)


def test_each_fixed_program_checks_itself(tmp_path):
    out = io.BytesIO()
    assert release.self_check("/Library/DocSuri/release/ops/bin/docsuri-ledger", stdout=out) == 0
    value = json.loads(out.getvalue())
    assert value["module"] == "backend.modules.operations.ledger_cli" and value["ok"] is True
    out = io.BytesIO()
    assert release.self_check("docsuri-unknown", stdout=out) == 2


# --- the review's findings of 2026-10-26 (R10, R12) --------------------------------------------


class Fails:
    """The release's operator, with each matching call (`when(operation, inputs, n)`, `n`
    counting the matching calls so far) failed through U7's injected permission fault, or
    raising `raises` instead when given."""

    def __init__(self, operator, when, *, raises: BaseException | None = None):
        self.operator, self.when, self.raises, self.count = operator, when, raises, 0

    def __getattr__(self, name):
        return getattr(self.operator, name)

    def execute(self, operation, target, inputs, *, key, **options):
        if self.when(operation, inputs, self.count):
            self.count += 1
            if self.raises is not None:
                raise self.raises
            return self.operator.execute(operation, target, inputs, key=key,
                                         injected_fault="permission")
        return self.operator.execute(operation, target, inputs, key=key, **options)


def starts(operation, inputs) -> bool:
    return operation == "platform.service.control" and inputs.get("action") == "start"


def again(stage) -> ReleaseInstall:
    return ReleaseInstall(stage.paths, stage.platform, clock=stage.clock)


class Terminal:
    """`/dev/tty` for `production_wiring.tty_confirm`: what it was shown, one answer."""

    def __init__(self, answer: bytes):
        self.answer, self.written = answer, b""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def write(self, data: bytes) -> None:
        self.written += data

    def readline(self, limit: int) -> bytes:
        return self.answer[:limit]


def test_the_installed_program_reads_the_tag_piped_and_the_hash_on_the_terminal(
        stage, monkeypatch):
    """Review finding (Major, R12): `echo '{"tag": …}' | sudo -k … docsuri-release install`
    reads the whole standard input first, so the typed short hash comes from the
    terminal, with the prompt there too, and standard output carries one JSON result."""
    import signal
    import sys

    from docsuri_ops import production_wiring as wiring

    for name in list(os.environ):
        if name.startswith(("PYTHON", "DYLD_", "LD_")):
            monkeypatch.delenv(name)
    terminal = Terminal(stage.github.commit[:12].encode() + b"\n")
    stage.platform.confirm = lambda shown: wiring.tty_confirm(shown, open_tty=lambda: terminal)
    monkeypatch.setattr(wiring, "release_install", lambda: stage.install)

    def program(word: str, document: dict) -> tuple[int, list[bytes]]:
        stdout = io.BytesIO()
        monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(
            json.dumps(document).encode())))
        monkeypatch.setattr(sys, "stdout", SimpleNamespace(buffer=stdout))
        before = signal.getsignal(signal.SIGHUP)
        code = release.main_fixed([word])
        assert signal.getsignal(signal.SIGHUP) == before  # the handlers come back
        return code, stdout.getvalue().splitlines()

    code, lines = program("install", {"tag": stage.tag})
    assert code == 0 and len(lines) == 1, lines
    assert json.loads(lines[0])["state"] == "installed"
    assert b"short hash" in terminal.written and stage.github.commit.encode() in terminal.written
    # `verify` takes its tag the same way (never a positional argument).
    terminal.written = b""
    code, lines = program("verify", {"tag": stage.tag})
    assert code == 0 and json.loads(lines[0])["state"] == "verified"
    # No terminal, or an end of input at the prompt: refused, one JSON result, unchanged.
    terminal.answer = b""
    code, lines = program("verify", {"tag": stage.tag})
    assert (code, json.loads(lines[0])["reason"]) == (1, "confirmation-unavailable")

    def no_terminal():
        raise OSError("no terminal")

    stage.platform.confirm = lambda shown: wiring.tty_confirm(shown, open_tty=no_terminal)
    code, lines = program("verify", {"tag": stage.tag})
    assert len(lines) == 1 and json.loads(lines[0])["reason"] == "confirmation-unavailable"
    assert run_program(["verify", stage.tag], {"tag": stage.tag})[1]["reason"] == "word-refused"


def test_a_hangup_or_a_terminate_signal_interrupts_and_answers_one_result(stage):
    import signal

    with release.interrupts(), pytest.raises(KeyboardInterrupt):
        os.kill(os.getpid(), signal.SIGHUP)
        for _ in range(1000):
            time_sleep(0.001)

    class Interrupting:
        def install(self, tag):
            raise KeyboardInterrupt()

        def recover(self):
            raise RuntimeError("anything")

    code, result = run_program(["install"], {"tag": stage.tag}, factory=Interrupting)
    assert (code, result["reason"]) == (130, "release-interrupted")
    assert result["offered"] == ["docsuri-release recover"]
    code, result = run_program(["recover"], {}, factory=Interrupting)
    assert (code, result["reason"], result["cause"]) == (1, "release-command-failed",
                                                          "RuntimeError")


def time_sleep(seconds: float) -> None:
    import time

    time.sleep(seconds)


def test_an_interrupt_in_the_readiness_wait_ends_the_record_and_recover_switches_back(stage):
    """Review finding (Major, R12): Ctrl-C (or SIGHUP, SIGTERM) during the readiness wait
    after the swap ends the ReleaseRecord, so the live exclusion is not left held;
    `recover` then switches the links back, starts v2 and routes the address back."""
    ready = stage.platform.ready

    def interrupted():
        raise KeyboardInterrupt()

    stage.platform.ready = interrupted
    with pytest.raises(KeyboardInterrupt):
        stage.install.install(stage.tag)
    record = stage.install.records.get(stage.tag)
    assert record["state"] == "failed" and record["reasonKey"] == "release-interrupted"
    assert stage.install.records.exclusion_blocker() is None
    assert stage.link() == stage.tag  # interrupted after the swap
    stage.platform.ready = ready
    result = again(stage).recover()
    assert result["state"] == "recovered" and result["record"] == "failed", result
    assert stage.link() == "v2.0.0" and result["ready"] is True
    assert set(services(stage).values()) == {"running"}
    assert stage.journey.tunnel()["origin"] == "v2-host"
    assert "reasonKey" not in stage.install.records.get(stage.tag)
    with pytest.raises(Refused, match="nothing-to-recover"):
        again(stage).recover()


def test_a_killed_install_left_installing_is_recovered_and_recover_waits_for_a_live_run(
        stage, monkeypatch):
    """A run killed outright (no handler ran) leaves its record `installing`, holding the
    live exclusion. `recover` is refused while a release command holds the run lock, and
    otherwise switches the links back and ends the record."""
    monkeypatch.setattr(ReleaseInstall, "_end_installing", lambda self, tag, reason: None)

    def killed():
        raise KeyboardInterrupt()

    ready = stage.platform.ready
    stage.platform.ready = killed
    with pytest.raises(KeyboardInterrupt):
        stage.install.install(stage.tag)
    monkeypatch.undo()
    assert stage.install.records.get(stage.tag)["state"] == "installing"
    assert stage.install.records.exclusion_blocker() == "release-install-active"
    stage.platform.ready = ready
    live = again(stage)
    with live._locked("install"), pytest.raises(Refused, match="release-run-active"):
        again(stage).recover()
    result = again(stage).recover()
    assert result["record"] == "switched-back" and stage.link() == "v2.0.0", result
    assert stage.install.records.exclusion_blocker() is None
    assert set(services(stage).values()) == {"running"}


def test_mode_failing_after_the_record_began_ends_it(stage):
    def broken():
        raise RuntimeError("profile unreadable")

    stage.platform.mode = broken
    error = refused(stage, "release-step-failed")
    assert error.facts == {"cause": "RuntimeError"}, error.facts
    record = stage.install.records.get(stage.tag)
    assert record["state"] == "failed" and record["reasonKey"] == "release-step-failed"
    assert stage.install.records.exclusion_blocker() is None and stage.link() == "v2.0.0"


def test_a_failure_inside_the_resume_still_ends_the_record_for_recover(stage):
    """The migration fails, then the resume's start raises something that is not a
    refusal: the record still ends (`resume-failed`), and `recover` starts v2."""
    stage.state["migrate"] = {"failed": {"owner": "accounts"}}
    stage.platform.operator = Fails(stage.platform.operator,
                                    lambda operation, inputs, n: starts(operation, inputs),
                                    raises=RuntimeError("store gone"))
    error = refused(stage, "migration-failed")
    assert error.changed is True and error.facts["resumeFailed"] == "resume-failed"
    record = stage.install.records.get(stage.tag)
    assert record["state"] == "failed" and record["reasonKey"] == "resume-failed", record
    assert stage.install.records.exclusion_blocker() is None
    assert set(services(stage).values()) == {"stopped"}
    stage.platform.operator = stage.platform.operator.operator
    result = again(stage).recover()
    assert result["state"] == "recovered" and set(services(stage).values()) == {"running"}
    assert stage.journey.tunnel()["origin"] == "v2-host" and stage.link() == "v2.0.0"


def test_a_stop_that_stopped_only_some_roles_starts_them_again(stage):
    """Review finding (Major, R12): the host stopped, then the workers' stop failed: the
    host is started again and the address routed back (before, only the route ran)."""
    failing = Fails(stage.platform.operator, lambda operation, inputs, n: (
        operation == "platform.service.control" and inputs.get("action") == "stop"
        and inputs.get("label") == LABELS[1]))
    stage.platform.operator = failing
    error = refused(stage, "service.control-failed")
    assert error.changed is True
    found = services(stage)
    assert found["host"] == "running" and found["workers"] is None, found
    assert stage.journey.tunnel()["origin"] == "v2-host" and stage.link() == "v2.0.0"
    assert stage.install.records.get(stage.tag)["state"] == "failed"


def test_a_start_that_fails_after_the_swap_switches_back(stage):
    failing = Fails(stage.platform.operator,
                    lambda operation, inputs, n: starts(operation, inputs) and n == 0)
    stage.platform.operator = failing
    result = stage.install.install(stage.tag)
    assert result["state"] == "switched-back" and result["cause"] == "service.control-failed"
    assert stage.link() == "v2.0.0"
    assert stage.install.records.get(stage.tag)["state"] == "switched-back"
    assert set(services(stage).values()) == {"running"}
    assert stage.journey.tunnel()["origin"] == "v2-host"
    assert stage.install.records.exclusion_blocker() is None


def test_a_route_back_that_fails_keeps_the_release_installed_and_recover_routes(stage):
    failing = Fails(stage.platform.operator, lambda operation, inputs, n: (
        operation == "platform.tunnel.route" and inputs.get("origin") == "v2-host" and n < 2))
    stage.platform.operator = failing
    result = stage.install.install(stage.tag)
    assert result["state"] == "installed" and result["routeBack"] == "failed", result
    assert result["offered"] == ["docsuri-release recover"] and failing.count == 2
    record = stage.install.records.get(stage.tag)
    assert record["state"] == "installed" and record["reasonKey"] == "route-back-failed"
    assert stage.link() == stage.tag and stage.journey.tunnel()["origin"] == "maintenance"
    recovered = again(stage).recover()
    assert recovered["record"] == "installed" and stage.link() == stage.tag, recovered
    assert stage.journey.tunnel()["origin"] == "v2-host"
    assert "reasonKey" not in stage.install.records.get(stage.tag)
    assert set(services(stage).values()) == {"running"}


def test_an_install_of_the_running_tag_is_refused_and_keeps_its_folder(stage):
    """Review finding (Major, R12): an install of the tag `release` points to is refused
    before staging (`tag-installed`), so the running release's folder stays whole."""
    stage.install.install(stage.tag)
    folder = stage.paths.releases / stage.tag
    before = sorted(path.name for path in folder.iterdir())
    error = refused(stage, "tag-installed")
    assert error.changed is False and error.facts["offered"] == ["verify", "rollback"]
    assert sorted(path.name for path in folder.iterdir()) == before
    assert stage.link() == stage.tag
    assert stage.install.records.get(stage.tag)["state"] == "installed"
    with pytest.raises(Refused, match="tag-installed"):
        stage.install.stage(stage.tag, stage.github.commit)


def test_a_reinstall_of_the_kept_tag_reuses_its_folder_with_no_clone_and_no_move(stage):
    """Your decision of 2026-10-26, "Reuse the kept folder" (Step 44 test item 5): after a
    rollback the tag's folder is `release-previous`'s. A reinstall of that tag reuses the
    folder as it stands (its identity names the tag and commit): no clone, no sync, no
    move, no `.kept-` folder, and the install completes on it."""
    stage.install.install(stage.tag)
    again(stage).rollback()
    folder = stage.paths.releases / stage.tag
    assert stage.link("release-previous") == stage.tag
    marker = folder / "kept-as-it-stands"
    marker.write_text("x")
    before = len(stage.calls)
    staged = again(stage).stage(stage.tag, stage.github.commit)
    assert staged["reused"] is True and staged["folder"] == folder
    assert stage.calls[before:] == []  # no clone, no sync
    assert marker.exists()
    assert not [path for path in stage.paths.releases.iterdir()
                if path.name.startswith(".kept-")]
    result = again(stage).install(stage.tag)
    assert result["state"] == "installed" and stage.link() == stage.tag
    assert ("clone", stage.tag) not in stage.calls[before:]
    assert marker.exists()


@pytest.mark.parametrize("differs", ["commit", "tag", "unreadable"])
def test_a_kept_folder_whose_identity_or_commit_differs_is_refused_and_left_whole(stage,
                                                                                differs):
    """The kept folder is never staged over: an identity naming another commit or tag is
    refused (`kept-release-differs`), one that cannot be read too
    (`kept-release-unreadable`), and the folder and both links stay as they were."""
    stage.install.install(stage.tag)
    again(stage).rollback()
    folder = stage.paths.releases / stage.tag
    identity = folder / release.RELEASE_IDENTITY
    if differs == "commit":
        release.write_identity(folder, stage.tag, "d" * 40, owner_uid=os.getuid())
    elif differs == "tag":
        release.write_identity(folder, "v2.0.0", stage.github.commit, owner_uid=os.getuid())
    else:
        identity.unlink()
    listing = sorted(path.name for path in folder.iterdir())
    before = len(stage.calls)
    error = refused(stage, "kept-release-unreadable" if differs == "unreadable"
                    else "kept-release-differs")
    assert error.changed is False
    assert sorted(path.name for path in folder.iterdir()) == listing
    assert stage.link() == "v2.0.0" and stage.link("release-previous") == stage.tag
    assert stage.calls[before:] == []
    assert stage.install.records.get(stage.tag)["state"] == "rolled-back"


def test_an_install_killed_during_staging_leaves_release_previous_whole(stage):
    """A run killed during the clone of another tag never touches the kept release: no
    folder a link points to is moved, and only the leftover of the killed staging is
    removed by the next install, which clones afresh."""
    stage.install.install(stage.tag)
    again(stage).rollback()
    kept = stage.paths.releases / stage.tag
    kept_listing = sorted(path.name for path in kept.iterdir())
    newer = second_tag(stage)
    clone = stage.platform.clone

    def killed(tag_name: str, folder: Path) -> None:
        clone(tag_name, folder)
        raise Interrupted()

    stage.platform.clone = killed
    with pytest.raises(Interrupted):
        again(stage).install(newer)
    assert stage.link() == "v2.0.0" and stage.link("release-previous") == stage.tag
    assert sorted(path.name for path in kept.iterdir()) == kept_listing
    assert release.folder_identity(kept) == {"tag": stage.tag, "commit": stage.github.commit}
    assert not [path for path in stage.paths.releases.iterdir()
                if path.name.startswith(".kept-")]
    # A leftover of the killed staging (no link points to it) is removed and cloned afresh.
    leftover = stage.paths.releases / newer
    leftover.mkdir(exist_ok=True)
    (leftover / "half-cloned").write_text("x")
    stage.platform.clone = clone
    assert again(stage).install(newer)["state"] == "installed"
    assert not (leftover / "half-cloned").exists() and ("clone", newer) in stage.calls
    assert stage.link() == newer and stage.link("release-previous") == "v2.0.0"
    # The kept release is no longer linked once the install completed: the record's
    # prune removes it, as it removes every folder neither link points to.
    assert not kept.exists()


def test_the_run_lock_is_read_without_a_password_while_a_command_runs(stage, monkeypatch):
    """Your decision of 2026-10-26, "Check the release run lock" (Step 44 test item 4),
    as the review's findings (Major, R19–R21) made it: the run lock each release command
    holds is a root-only file (0600), and its presence is a separate marker anyone may
    read (0644: the command's pid, word and start) written right after the lock is taken
    and removed at the command's end; `release_run_active` reads the marker, never locks
    it, and answers `release-run-active` exactly while the command's process lives. No
    marker, or a removed one, answers None; a marker that cannot be read (a link in its
    place, no JSON, no pid) refuses rather than admits; a marker whose process is gone
    (a command that died) is refused as stale until the next release command, which
    replaces it under the real lock."""
    import stat
    import subprocess
    import sys

    from docsuri_ops.release import release_run_active, run_lock_path, run_marker_path

    assert release_run_active(stage.paths) is None  # no command ever ran
    marker = run_marker_path(stage.paths)
    with stage.install._locked("install"):
        path = run_lock_path(stage.paths)
        assert stat.S_IMODE(path.stat().st_mode) == 0o600  # no other account opens it
        assert stat.S_IMODE(marker.stat().st_mode) == 0o644  # anyone reads this
        written = json.loads(marker.read_bytes())
        assert written["pid"] == os.getpid() and written["word"] == "install"
        assert written["startedAt"] == stage.clock().isoformat()
        assert release_run_active(stage.paths) == "release-run-active"
        with pytest.raises(Refused, match="release-run-active"):
            with again(stage)._locked("verify"):
                pass
        assert marker.exists()  # the refused command never touched the marker
    assert not marker.exists() and release_run_active(stage.paths) is None
    # Error cases: a link in the marker's place, no JSON, no pid.
    os.symlink(stage.paths.releases / "v2.0.0", marker)
    assert release_run_active(stage.paths) == "release-run-lock-unreadable"
    marker.unlink()
    marker.write_text("{not json")
    assert release_run_active(stage.paths) == "release-run-lock-unreadable"
    marker.write_text(json.dumps({"word": "install"}))
    assert release_run_active(stage.paths) == "release-run-lock-unreadable"
    # A marker left by a command that died: refused as stale, until the next command.
    gone = subprocess.Popen([sys.executable, "-c", "pass"])
    gone.wait()
    marker.write_text(json.dumps({"pid": gone.pid, "word": "install",
                                  "startedAt": stage.clock().isoformat()}))
    assert release_run_active(stage.paths) == "release-run-marker-stale"
    with again(stage)._locked("recover"):
        assert json.loads(marker.read_bytes())["word"] == "recover"
        assert release_run_active(stage.paths) == "release-run-active"
    assert release_run_active(stage.paths) is None
    # A live process of another account (EPERM) is a live command, fail closed.
    def refused(pid, signal_number):
        raise PermissionError()

    monkeypatch.setattr(os, "kill", refused)
    marker.write_text(json.dumps({"pid": 1, "word": "install"}))
    assert release_run_active(stage.paths) == "release-run-active"
    marker.unlink()


def test_a_reader_holding_the_readable_file_can_no_longer_block_a_command(stage):
    """Review findings (Major, R19–R21): `flock` needs no write access, so a lock any
    account could open read-only was one any account could hold. Now the lock is a file
    no other account can open, and the file anyone may read is a marker that readers
    never lock: a read-only descriptor holding `LOCK_EX` on it neither refuses `_locked`
    nor makes `release_run_active` answer `release-run-active`, and a command holding
    the lock is still reported exactly while it runs."""
    import fcntl

    from docsuri_ops.release import release_run_active, run_marker_path

    marker = run_marker_path(stage.paths)
    with stage.install._locked("install"):
        reader = os.open(marker, os.O_RDONLY | os.O_NOFOLLOW)
        fcntl.flock(reader, fcntl.LOCK_EX | fcntl.LOCK_NB)  # held by a reader, as before
        assert release_run_active(stage.paths) == "release-run-active"  # read, not locked
    # The command ended: the reader's hold on the old marker refuses nothing.
    assert release_run_active(stage.paths) is None
    with again(stage)._locked("verify"):
        assert release_run_active(stage.paths) == "release-run-active"
    assert release_run_active(stage.paths) is None
    os.close(reader)


def test_a_rollback_refuses_a_kept_folder_whose_identity_cannot_be_read(stage):
    """`rollback` reads the kept release's identity before anything changes: a kept folder
    without one, or with a damaged one, is refused (`kept-release-unreadable`), and a
    kept folder whose record is rolled-back is refused as a failed one is."""
    stage.install.install(stage.tag)
    base = stage.paths.releases / "v2.0.0"
    (base / release.RELEASE_IDENTITY).unlink()
    with pytest.raises(Refused, match="kept-release-unreadable"):
        again(stage).rollback()
    (base / release.RELEASE_IDENTITY).write_text("{not json")
    with pytest.raises(Refused, match="kept-release-unreadable"):
        again(stage).rollback()
    assert stage.link() == stage.tag and set(services(stage).values()) == {"running"}
    assert stage.install.records.get(stage.tag)["state"] == "installed"
    release.write_identity(base, "v2.0.0", stage.github.commit, owner_uid=os.getuid())
    assert again(stage).rollback()["state"] == "rolled-back"
    assert stage.link() == "v2.0.0"
    # Back on the base release, the kept one is the rolled-back release: refused.
    stage.install.records.begin("v2.0.0", stage.github.commit, previous_tag=None)
    stage.install.records.finish("v2.0.0", "installed")
    with pytest.raises(Refused) as caught:
        again(stage).rollback()
    assert caught.value.reason == "kept-release-failed"
    assert caught.value.facts == {"keptRelease": stage.tag, "keptState": "rolled-back"}


def test_a_rollback_refuses_one_folder_a_missing_one_and_follows_the_links(stage):
    stage.install.install(stage.tag)
    current = Path(os.readlink(stage.paths.release))
    release._relink(stage.paths.release_previous, current)  # both links at one folder
    with pytest.raises(Refused, match="no-kept-release"):
        again(stage).rollback()
    release._relink(stage.paths.release_previous, stage.paths.releases / "v0.0.1")
    with pytest.raises(Refused, match="no-kept-release"):
        again(stage).rollback()
    # The release rolled back is the one `release` points to, not the latest record.
    release._relink(stage.paths.release_previous, stage.paths.releases / stage.tag)
    release._relink(stage.paths.release, stage.paths.releases / "v2.0.0")
    with pytest.raises(Refused, match="no-installed-release"):
        again(stage).rollback()
    assert stage.link() == "v2.0.0"


def test_a_rollback_after_a_failed_apply_has_nothing_to_roll_back(tmp_path, realm):
    stage = stage_for(tmp_path, realm, version=2)
    try:
        stage.state["installer"] = {"failed": "rule-files"}
        refused(stage, "arrangement-apply-failed")
        assert stage.link() == "v2.0.0"  # the links never moved: v2.0.0 keeps running
        with pytest.raises(Refused, match="no-kept-release"):
            again(stage).rollback()
    finally:
        stage.platform.ledger.close()


def test_a_begin_refusal_is_a_refusal_not_a_traceback(stage):
    stage.state["migrate"] = {"failed": {"owner": "accounts"}}
    refused(stage, "migration-failed")
    stage.state["migrate"] = {"applied": []}
    moved = secrets.token_hex(20)  # the tag now names another commit
    stage.github.tags[stage.tag]["sha"] = moved
    stage.github.main.add(moved)
    error = refused(stage, "tag-commit-differs")
    assert error.changed is False
    code, result = run_program(["install"], {"tag": stage.tag}, factory=lambda: stage.install)
    assert (code, result["reason"]) == (1, "tag-commit-differs")


def test_a_switch_back_whose_stop_fails_ends_the_record_and_recover_stops_v2(stage):
    """Review finding (Major, R10), with your decision of 2026-10-26 ("Leave v2
    stopped"): the release installed while v2 was kept stopped fails its probe at the
    soak's start, and the switch back's stops fail, so v2 is not known to be stopped (the
    switch back starts nothing). The verification was never recorded on the
    CutoverRecord (an install made while v2 is kept stopped records none, review finding,
    Major, R13), the install record ends (`switched-back`, `switch-back-failed`), and its
    `probePending` stays, since the failed release still runs (review finding, Major,
    R15). The CutoverRecord names the linked tag; `verify` on that tag, which the
    runbooks name next, starts no v2 and no soak while the record waits for `recover`
    (`recover-required`); `recover` leaves v2 stopped, since only the soak's start starts
    it while the record is rolled-back, and then `verify` starts the soak."""
    from docsuri_ops.release import unprobed_tag

    machine = installed_while_stopped(stage)
    stage.state["probe"] = False

    def when(operation, inputs, n):
        return operation == "platform.service.control" and inputs.get("action") == "stop"

    failing = Fails(stage.platform.operator, when)
    stage.platform.operator = failing
    moved = stage.install.verify(stage.tag)["verification"]["cutover"]
    assert moved["probe"] == "failed" and moved["reason"] == "release-probe-failed", moved
    assert moved["switchedBack"]["state"] == "failed"
    assert moved["switchedBack"]["reason"] == "switch-back-failed"
    assert stage.link() == "v2.0.0"
    record = stage.install.records.get(stage.tag)
    assert record["state"] == "switched-back" and record["reasonKey"] == "switch-back-failed"
    assert record["probePending"] is True  # the failed release may still run
    assert set(services(stage).values()) == {"running"}  # the stops failed
    cutover = machine.require()
    assert cutover["releaseTag"] == "v2.0.0" and "verificationRunId" not in cutover
    assert "soakStartedAt" not in cutover and cutover["state"] == "rolled-back"
    assert unprobed_tag(stage.platform.ledger, stage.paths, clock=stage.clock) is None
    # `cutover check` then starts no soak: the record holds no passed verification.
    from docsuri_ops.cutover.tool import CutoverTool

    assert CutoverTool.soak_report(SimpleNamespace(machine=machine)) == {"soak": None}
    # Nor would it with a verification on the record: the release record waits for
    # `recover`.
    verified_record = SimpleNamespace(
        require=lambda: {**machine.require(), "verificationRunId": str(uuid4())},
        ledger=stage.platform.ledger)
    report = CutoverTool.soak_report(SimpleNamespace(machine=verified_record))
    assert report["soak"] is None and report["v2Start"]["reason"] == "recover-required"
    stage.platform.operator = failing.operator
    # `verify` on the linked tag starts nothing until `recover` ran.
    release.write_identity(stage.paths.releases / "v2.0.0", "v2.0.0", stage.github.commit,
                           owner_uid=os.getuid())
    stage.github.tags["v2.0.0"] = dict(stage.github.tags[stage.tag])
    stage.state["probe"] = True
    held = ReleaseInstall(stage.paths, stage.platform, clock=stage.clock).verify("v2.0.0")
    assert held["verification"]["cutover"] == {"state": "rolled-back",
                                               "reason": "recover-required"}, held
    assert "start-rehearsal-v2" not in held["steps"]
    assert "soakStartedAt" not in machine.require()
    assert "verificationRunId" not in machine.require()
    result = again(stage).recover()
    assert result["record"] == "switched-back" and result["v2"] == "stopped", result
    assert set(services(stage).values()) == {"stopped"}
    ended = stage.install.records.get(stage.tag)
    assert "probePending" not in ended and "reasonKey" not in ended
    verified = ReleaseInstall(stage.paths, stage.platform, clock=stage.clock).verify("v2.0.0")
    moved = verified["verification"]["cutover"]
    assert moved == {"state": "rehearsing", "soak": "started", "ready": True}, moved
    assert set(services(stage).values()) == {"running"}


def test_a_live_switch_back_whose_stop_fails_keeps_the_maintenance_notice(stage):
    """Review finding (Major, R15): a live install whose probe journey fails, and whose
    switch back's stops then fail, leaves v2 running the failed release: nothing is
    started, the public address stays on the maintenance notice (never routed to the
    failed release's processes), and the command answers `switch-back-failed` with
    `recover` offered; `recover` stops and starts v2 on the linked release and routes the
    address back."""
    switching = {"on": False}

    def probe() -> bool:
        switching["on"] = True  # the switch back begins after this failed probe
        return False

    def when(operation, inputs, n):
        return switching["on"] and operation == "platform.service.control" and inputs.get(
            "action") == "stop"

    stage.platform.probe = probe
    failing = Fails(stage.platform.operator, when)
    stage.platform.operator = failing
    error = refused(stage, "switch-back-failed")
    assert error.facts["offered"] == ["docsuri-release recover"], error.facts
    assert stage.journey.tunnel()["origin"] == "maintenance"
    assert stage.link() == "v2.0.0"  # relinked, but the failed release still runs
    record = stage.install.records.get(stage.tag)
    assert record["state"] == "switched-back" and record["reasonKey"] == "switch-back-failed"
    assert set(services(stage).values()) == {"running"}
    stage.platform.operator = failing.operator
    result = again(stage).recover()
    assert result["record"] == "switched-back" and result["ready"] is True, result
    assert stage.journey.tunnel()["origin"] == "v2-host"
    assert "reasonKey" not in stage.install.records.get(stage.tag)


def test_an_unprobed_record_blocks_the_soak_whatever_the_links_show(stage):
    """`unprobed_tag` fails closed: a record still waiting for its probe journey blocks
    the soak even when the links point elsewhere, and `recover` ends it."""
    from docsuri_ops.release import unprobed_tag

    installed_while_stopped(stage)
    release._relink(stage.paths.release, stage.paths.releases / "v2.0.0")
    assert unprobed_tag(stage.platform.ledger, stage.paths, clock=stage.clock) == stage.tag
    result = again(stage).recover()
    assert result["record"] == "switched-back", result
    assert unprobed_tag(stage.platform.ledger, stage.paths, clock=stage.clock) is None


class Interrupted(BaseException):
    """The run's process ending inside an effect."""


class ServiceEffects:
    """The release's operator, with v2's service stops run through a run effect of the
    case's own (`effect`), so a stop is interrupted after its receipt was bound."""

    def __init__(self, operator, effect):
        from docsuri_ops.u8_platform.u8_protocols import Operator

        self.operator, self.effect, self.ran = operator, effect, []
        self.clone = Operator(operator.profile, operator.store, actor=operator.actor,
                              authorities=operator.authorities, facts=operator.facts,
                              run_effect=self._run)

    def _run(self, **options):
        self.ran.append(options["operation_id"])
        return self.effect(**options)

    def __getattr__(self, name):
        return getattr(self.operator, name)

    def execute(self, operation, target, inputs, *, key, **options):
        if (self.effect is not None and operation == "platform.service.control"
                and inputs.get("action") == "stop"):
            return self.clone.execute(operation, target, inputs, key=key, **options)
        return self.operator.execute(operation, target, inputs, key=key, **options)


def test_an_earlier_runs_stop_still_in_its_lease_refuses_the_next_install(stage):
    """Review finding (Major, R12): a stop the first run left in flight is kept in the
    journal; the next run settles it by its own key before opening any of its own, and
    it is still within its lease, so the install is refused (`effect-in-progress`) and
    nothing runs beside it."""

    def interrupted(**options):
        raise Interrupted()

    effects = ServiceEffects(stage.platform.operator, interrupted)
    stage.platform.operator = effects
    with pytest.raises(Interrupted):
        stage.install.install(stage.tag)
    assert len(effects.ran) == 1
    effects.effect = None
    try:
        error = refused(stage, "effect-in-progress")
        assert error.changed is False and len(effects.ran) == 1
        assert services(stage) == dict.fromkeys(("host", "workers", "scheduler"))
        assert stage.install.records.exclusion_blocker() is None
    finally:
        effects.store.settle_operation(operation_id=effects.ran[0], outcome="failed",
                                       disposition="not-applied", effect_refs=[])
    # Settled (here as nothing applied), the next install goes on.
    assert again(stage).install(stage.tag)["state"] == "installed"


def test_an_earlier_backup_without_its_bound_operation_is_never_taken_again(stage):
    """A pending backup the journal holds with no bound operation (a platform that names
    none) cannot be settled by a receipt: the next install never asks for that set
    again, and takes its own."""
    from backend.modules.operations.recovery_procedures import OutcomeUnknown

    keys: list[str] = []

    def unknown(tag: str, key: str) -> dict:
        keys.append(key)
        raise OutcomeUnknown(str(uuid4()))

    stage.platform.backup = unknown
    refused(stage, "pre-release-backup-failed")
    (first,) = keys

    def settles(tag: str, key: str) -> dict:
        keys.append(key)
        return {"integrity": "passed", "backupId": str(uuid4())}

    stage.platform.backup = settles
    assert again(stage).install(stage.tag)["state"] == "installed"
    assert len(keys) == 2 and keys[1] != first
    journal = json.loads((stage.paths.control / "releases" / release.EFFECT_JOURNAL)
                         .read_bytes())["entries"]
    assert all(entry["state"] == "settled" for entry in journal)


class BackupEffects:
    """The recovery procedures' operator, with its backups run through a run effect of
    the case's own: the release run is interrupted after the set's receipt was bound,
    inside the agent's longest step (the operation left executing in U7's store), and
    every backup the operator is asked for is counted."""

    def __init__(self, operator):
        self.operator, self.real, self.bound, self.asked = operator, operator.run_effect, [], []
        operator.run_effect = self._run

    def _run(self, **options):
        if options["operation_name"] == "platform.database.backup":
            self.bound.append(options["operation_id"])
            raise Interrupted()
        return self.real(**options)

    def restore(self) -> None:
        self.operator.run_effect = self.real


def backup_receipt(operator, operation_id: str) -> dict:
    from docsuri_ops.u8_platform.u8_protocols import ReceiptReader

    held = operator._read_named(operation_id)
    return {"outcome": ReceiptReader.outcome(held),
            "reconciliationState": held.get("reconciliationState")}


def unresolved_ids(operator) -> set[str]:
    """Every receipt PlatformControl still holds as unresolved for the operator."""
    found: set[str] = set()
    for authority in set(operator.authorities.values()):
        found |= {str(item["operationId"])
                  for item in operator.store.list_unresolved(operator.actor, authority)}
    return found


def test_a_backup_interrupted_mid_effect_refuses_recover_in_its_lease_then_settles(backed,
                                                                                    realm):
    """Review finding (Major, R14): Ctrl-C (or SIGHUP, SIGTERM) inside the backup after
    writes stop leaves its receipt bound and its operation executing. Within its lease,
    `recover` is refused (`effect-in-progress`) before anything changes, so nothing runs
    beside the set; once the lease has passed, `recover` settles it by its receipt (the
    procedures' operator reconciles it from its target, not applied, so PlatformControl
    no longer holds it unresolved), never takes it again, and puts v2 back."""
    from tests.u8_service_operations_integration.component.test_cutover_words import (
        lease_passed,
    )

    stage = backed.stage
    operator = backed.procedures.platform.operator
    effects = BackupEffects(operator)
    try:
        with pytest.raises(Interrupted):
            stage.install.install(stage.tag)
    finally:
        effects.restore()
    (bound,) = effects.bound
    record = stage.install.records.get(stage.tag)
    assert record["state"] == "failed" and record["reasonKey"] == "release-interrupted"
    assert set(services(stage).values()) == {"stopped"}
    journal = json.loads((stage.paths.control / "releases" / release.EFFECT_JOURNAL)
                         .read_bytes())["entries"]
    (pending,) = [entry for entry in journal if entry["kind"] == "backup"]
    assert pending["state"] == "pending" and pending["effect"]["target"] == (
        "database-production")
    with pytest.raises(Refused) as within:
        again(stage).recover()
    assert within.value.reason == "effect-in-progress" and within.value.changed is False
    assert set(services(stage).values()) == {"stopped"}  # nothing ran beside it
    assert sets(stage, "live") == []
    lease_passed(realm, bound)
    result = again(stage).recover()
    assert result["state"] == "recovered" and result["ready"] is True, result
    assert backup_receipt(operator, bound) == {"outcome": "failed",
                                               "reconciliationState": "reconciled-not-applied"}
    assert bound not in unresolved_ids(operator)  # PlatformControl is not degraded by it
    assert sets(stage, "live") == []  # the set was never taken again
    assert set(services(stage).values()) == {"running"}
    assert stage.journey.tunnel()["origin"] == "v2-host"
    journal = json.loads((stage.paths.control / "releases" / release.EFFECT_JOURNAL)
                         .read_bytes())["entries"]
    assert all(entry["state"] == "settled" for entry in journal)


def test_a_run_stopped_before_its_backup_was_bound_takes_no_backup_at_settle(backed):
    """The run stopped after its journal entry was written and before the set was bound:
    the next command's settle finds its bound input absent, so nothing runs for it (no
    new production backup under the old key, before any stop), and the install that
    follows takes its own set once."""
    stage = backed.stage
    operator = backed.procedures.platform.operator
    asked: list[str] = []
    execute = operator.execute

    def counted(operation, target, inputs, *, key, **options):
        if operation == "platform.database.backup":
            asked.append(key)
        return execute(operation, target, inputs, key=key, **options)

    operator.execute = counted
    real = stage.platform.backup

    def stopped(tag: str, key: str) -> dict:
        raise Interrupted()

    stage.platform.backup = stopped
    try:
        with pytest.raises(Interrupted):
            stage.install.install(stage.tag)
        journal = json.loads((stage.paths.control / "releases" / release.EFFECT_JOURNAL)
                             .read_bytes())["entries"]
        (pending,) = [entry for entry in journal if entry["kind"] == "backup"]
        assert pending["state"] == "pending" and "effect" in pending
        stage.platform.backup = real
        result = again(stage).recover()
        assert result["state"] == "recovered", result
        assert asked == [] and sets(stage, "live") == []  # no backup ran at the settle
        assert again(stage).install(stage.tag)["state"] == "installed"
        assert len(asked) == 1 and asked[0] != pending["effect"]["key"]
        (taken,) = sets(stage, "live")
        assert taken["integrity"] == "passed"
    finally:
        operator.execute = execute


# --- the second review's findings of 2026-10-26 (Minor, R13 and R14) ---------------------


def test_a_pending_probe_blocks_the_soak_whichever_installed_record_is_the_latest(stage):
    """Review finding (Minor, R13): `unprobed_tag` scans every installed record. A later
    change to an older installed record (here `recover` finishing it) makes that one the
    latest, and the release still waiting for its probe keeps blocking the soak; a later
    install supersedes it, and a release rollback to it makes it wait again."""
    from docsuri_ops.release import unprobed_tag

    installed_while_stopped(stage)
    records = stage.install.records
    stage.platform.sleep(60)
    records.begin("v2.0.0", stage.github.commit, previous_tag=None)
    records.finish("v2.0.0", "installed")
    assert records.installed()["releaseTag"] == "v2.0.0"  # the latest installed record
    assert unprobed_tag(stage.platform.ledger, stage.paths, clock=stage.clock) == stage.tag
    # Error case: `cutover check` reads the same answer, so no soak starts.
    from docsuri_ops.cutover.tool import CutoverTool

    machine = Cutover(stage.platform.ledger, SYNTHETIC_OPERATIONS, clock=stage.clock)
    verified = SimpleNamespace(require=lambda: {**machine.require(),
                                                "verificationRunId": str(uuid4())},
                               ledger=stage.platform.ledger)
    platform = SimpleNamespace(evidence=None, release_unprobed=lambda: unprobed_tag(
        stage.platform.ledger, stage.paths, clock=stage.clock))
    report = CutoverTool.soak_report(SimpleNamespace(machine=verified, platform=platform))
    assert report["v2Start"]["reason"] == "release-not-probed", report
    assert report["v2Start"]["releaseTag"] == stage.tag


def test_a_later_install_supersedes_a_pending_probe_and_a_rollback_restores_it(stage):
    """With every installed record scanned, a release still waiting when a later install
    moved it to `release-previous` would block every soak behind a release that no longer
    runs: the later install supersedes it (`probeSuperseded`), and a release rollback that
    links it again makes it wait for its probe again."""
    from docsuri_ops.release import unprobed_tag

    installed_while_stopped(stage)
    later = second_tag(stage)
    stage.platform.sleep(60)  # the later install's record is the later one
    result = ReleaseInstall(stage.paths, stage.platform, clock=stage.clock).install(later)
    assert result["state"] == "installed", result
    superseded = stage.install.records.get(stage.tag)
    assert "probePending" not in superseded and superseded["probeSuperseded"] is True
    assert stage.install.records.installed()["releaseTag"] == later
    assert unprobed_tag(stage.platform.ledger, stage.paths, clock=stage.clock) is None
    rolled = ReleaseInstall(stage.paths, stage.platform, clock=stage.clock).rollback()
    assert rolled["state"] == "rolled-back" and stage.link() == stage.tag, rolled
    waiting = stage.install.records.get(stage.tag)
    assert waiting["probePending"] is True and "probeSuperseded" not in waiting
    assert unprobed_tag(stage.platform.ledger, stage.paths, clock=stage.clock) == stage.tag


def test_a_relink_that_fails_after_a_failed_probe_is_completed_by_recover(stage,
                                                                          monkeypatch):
    """Review finding (Minor, R13): in the soak-start switch back, a relink that fails
    leaves the record `installed` and waiting for its probe with `switch-back-failed`, the
    links still on the failed release; `recover` points them at the kept release, ends the
    record switched back and leaves v2 stopped (the cutover is rolled-back)."""
    from docsuri_ops.release import unprobed_tag

    installed_while_stopped(stage)
    stage.state["probe"] = False
    relink = release._relink

    def fails(link, target):
        if link == stage.paths.release:
            raise OSError("relink failed")
        return relink(link, target)

    monkeypatch.setattr(release, "_relink", fails)
    moved = stage.install.verify(stage.tag)["verification"]["cutover"]
    assert moved["switchedBack"]["state"] == "failed", moved
    assert moved["switchedBack"]["step"] == "relink-failed"
    record = stage.install.records.get(stage.tag)
    assert record["state"] == "installed" and record["probePending"] is True
    assert record["reasonKey"] == "switch-back-failed" and stage.link() == stage.tag
    assert unprobed_tag(stage.platform.ledger, stage.paths, clock=stage.clock) == stage.tag
    monkeypatch.setattr(release, "_relink", relink)
    result = again(stage).recover()
    assert result["record"] == "switched-back" and result["v2"] == "stopped", result
    assert stage.link() == "v2.0.0" and stage.link("release-previous") == "v2.0.0"
    ended = stage.install.records.get(stage.tag)
    assert ended["state"] == "switched-back" and "probePending" not in ended
    assert set(services(stage).values()) == {"stopped"}
    with pytest.raises(Refused, match="nothing-to-recover"):
        again(stage).recover()


def rolled_back_running(stage) -> None:
    """Rolled-back with an accepted dry run and no soak yet, v2 running (a soak start
    that was not ready, say): the state where only the soak's start may start v2."""
    rolled_back(stage)
    stage.platform.mode = lambda: "rehearsal"
    for label in LABELS:
        stage.platform.operator.execute("platform.service.control", label,
                                        {"label": label, "action": "start"},
                                        key=f"test-running:{uuid4().hex}:{label}")
    assert set(services(stage).values()) == {"running"}


def test_an_install_whose_backup_fails_while_rolled_back_leaves_v2_stopped(stage):
    """Review finding (Minor, R13): the install's way out before the swap reads the
    CutoverRecord as a release rollback does, so with the record rolled-back (an accepted
    dry run, no soak) it starts nothing again."""
    rolled_back_running(stage)
    stage.platform.backup = lambda tag, key: {"integrity": "failed", "reason": "agent-busy"}
    error = refused(stage, "pre-release-backup-failed")
    assert error.changed is True
    assert set(services(stage).values()) == {"stopped"}
    assert stage.link() == "v2.0.0"
    assert stage.install.records.get(stage.tag)["state"] == "failed"
    assert stage.install.records.exclusion_blocker() is None


def test_an_install_whose_probe_fails_while_rolled_back_switches_back_with_v2_stopped(stage):
    rolled_back_running(stage)
    stage.state["probe"] = False
    result = stage.install.install(stage.tag)
    assert result["state"] == "switched-back" and result["v2"] == "stopped", result
    assert stage.link() == "v2.0.0"
    assert set(services(stage).values()) == {"stopped"}
    machine = Cutover(stage.platform.ledger, SYNTHETIC_OPERATIONS, clock=stage.clock)
    assert "soakStartedAt" not in machine.require()


def test_a_way_out_starts_only_the_roles_the_stop_found_running(stage):
    """Review finding (Minor, R13): a role stopped in person before the install stays
    stopped through the install's way out; the fixed program's `wasLoaded` says which
    roles the install's stop actually stopped."""
    stage.platform.operator.execute("platform.service.control", LABELS[1],
                                    {"label": LABELS[1], "action": "stop"},
                                    key=f"test-in-person-stop:{uuid4().hex}")
    stage.state["migrate"] = {"failed": {"owner": "accounts"}}
    refused(stage, "migration-failed")
    found = services(stage)
    assert found == {"host": "running", "workers": "stopped", "scheduler": "running"}, found


def test_a_failure_that_is_not_a_refusal_inside_the_switch_back_is_recoverable(stage):
    """Review finding (Minor, R13): a store or ledger error raised inside the switch back's
    stop is one of its failures, so the record still ends with `switch-back-failed`; and a
    run whose failure escaped the switch back altogether (ended `failed` with the links at
    its release) is still found by `recover`, which points the links back."""
    switching = {"on": False}

    def probe() -> bool:
        switching["on"] = True
        return False

    stage.platform.probe = probe
    failing = Fails(stage.platform.operator, lambda operation, inputs, n: (
        switching["on"] and operation == "platform.service.control"
        and inputs.get("action") == "stop" and n == 0), raises=RuntimeError("store gone"))
    stage.platform.operator = failing
    error = refused(stage, "switch-back-failed")
    assert error.facts["step"] == "switch-back-stop-failed", error.facts
    record = stage.install.records.get(stage.tag)
    assert record["state"] == "switched-back" and record["reasonKey"] == "switch-back-failed"
    stage.platform.operator = failing.operator
    assert again(stage).recover()["state"] == "recovered"


def test_a_failure_escaping_the_switch_back_leaves_a_record_recover_reaches(stage,
                                                                           monkeypatch):
    def escapes(self, *args, **options):
        raise RuntimeError("ledger gone")

    stage.state["probe"] = False
    monkeypatch.setattr(ReleaseInstall, "_switch_back", escapes)
    error = refused(stage, "release-step-failed")
    assert error.changed is True
    record = stage.install.records.get(stage.tag)
    assert record["state"] == "failed" and record["reasonKey"] == "release-step-failed"
    assert stage.link() == stage.tag  # the links still at the failed release
    monkeypatch.undo()
    result = again(stage).recover()
    assert result["state"] == "recovered" and result["record"] == "failed", result
    assert stage.link() == "v2.0.0" and set(services(stage).values()) == {"running"}


def test_an_effect_in_progress_refusal_leaves_the_records_as_they_were(stage):
    """Review finding (Minor, R14): what an earlier run left in flight is settled before a
    record begins, so the refusal changes no record: the install's record is not ended
    `failed`, and a rollback's installed record is not marked for `recover`."""

    def interrupted(**options):
        raise Interrupted()

    stage.install.install(stage.tag)
    effects = ServiceEffects(stage.platform.operator, interrupted)
    stage.platform.operator = effects
    with pytest.raises(Interrupted):
        again(stage).rollback()
    before = stage.install.records.get(stage.tag)
    assert before["state"] == "installed"
    effects.effect = None
    try:
        for word in (lambda: again(stage).rollback(), lambda: again(stage).install(
                second_tag(stage))):
            with pytest.raises(Refused) as caught:
                word()
            assert caught.value.reason == "effect-in-progress" and not caught.value.changed
            assert stage.install.records.get(stage.tag) == before
        assert [record["releaseTag"] for record in stage.platform.ledger.records(
            "release-record")] == [stage.tag]
    finally:
        effects.store.settle_operation(operation_id=effects.ran[0], outcome="failed",
                                       disposition="not-applied", effect_refs=[])
    assert again(stage).rollback()["state"] == "rolled-back"


def test_ctrl_c_before_the_record_began_answers_nothing_changed(stage):
    """Review finding (Minor, R14): Ctrl-C at step 0's prompt changes nothing and offers
    nothing."""

    def interrupted(shown):
        raise KeyboardInterrupt()

    stage.platform.confirm = interrupted
    code, result = run_program(["install"], {"tag": stage.tag}, factory=lambda: stage.install)
    assert (code, result) == (130, {"ok": False, "reason": "release-interrupted",
                                    "changed": False})
    assert stage.install.records.get(stage.tag) is None


def test_a_completed_install_clears_what_earlier_runs_left_for_recover(stage):
    """Review finding (Minor, R14): a route back that failed long ago is no longer acted
    on once a later install completed: `recover` answers `nothing-to-recover` instead of
    stopping and starting production v2 for it."""
    failing = Fails(stage.platform.operator, lambda operation, inputs, n: (
        operation == "platform.tunnel.route" and inputs.get("origin") == "v2-host" and n < 2))
    stage.platform.operator = failing
    assert stage.install.install(stage.tag)["routeBack"] == "failed"
    stage.platform.operator = failing.operator
    later = second_tag(stage)
    assert again(stage).install(later)["state"] == "installed"
    assert "reasonKey" not in stage.install.records.get(stage.tag)
    with pytest.raises(Refused, match="nothing-to-recover"):
        again(stage).recover()


def test_an_interrupted_verify_stops_what_it_started_and_verify_completes_it(stage):
    """Review finding (Minor, R14): Ctrl-C during the soak gate's readiness wait stops the
    roles the `verify` started, leaves the record waiting for its probe, and offers
    `verify` (`recover` has nothing to do); the next `verify` probes and starts the soak."""
    installed_while_stopped(stage)
    ready = stage.platform.ready

    def interrupted():
        raise KeyboardInterrupt()

    stage.platform.ready = interrupted
    code, result = run_program(["verify"], {"tag": stage.tag}, factory=lambda: again(stage))
    assert (code, result["reason"], result["changed"]) == (130, "release-interrupted", True)
    assert result["offered"] == ["docsuri-release verify"]
    assert set(services(stage).values()) == {"stopped"}
    record = stage.install.records.get(stage.tag)
    assert record["probePending"] is True and "reasonKey" not in record
    with pytest.raises(Refused, match="nothing-to-recover"):
        again(stage).recover()
    stage.platform.ready = ready
    moved = again(stage).verify(stage.tag)["verification"]["cutover"]
    assert moved == {"state": "rehearsing", "soak": "started", "ready": True,
                     "probe": "passed"}, moved


# --- the third review's findings of 2026-10-26 (R18) --------------------------------------------


def superseded_by_a_later_install(stage) -> str:
    """The installed-while-stopped release (its probe pending) superseded by a later tag's
    completed install, which started v2 and the soak; answers the later tag."""
    installed_while_stopped(stage)
    later = second_tag(stage)
    stage.platform.sleep(60)  # the later install's record is the later one
    assert again(stage).install(later)["state"] == "installed"
    assert stage.install.records.get(stage.tag)["probeSuperseded"] is True
    return later


@pytest.mark.parametrize("how", ["fails", "interrupted"])
def test_a_rollback_to_a_superseded_release_that_stops_after_its_relink_leaves_it_pending(
        stage, how):
    """Review finding (Minor, R18): the kept release is marked pending again as soon as
    `release` points at it, so a rollback whose start fails after the relink, or one
    interrupted there, leaves the linked release waiting for its probe (`probePending`,
    no `probeSuperseded`), and `verify` then probes it before any soak; `recover` ends
    the rollback's record and leaves the pending mark in place."""
    from docsuri_ops.release import unprobed_tag

    later = superseded_by_a_later_install(stage)
    interrupted = KeyboardInterrupt() if how == "interrupted" else None
    failing = Fails(stage.platform.operator, lambda operation, inputs, n: starts(operation,
                                                                                 inputs),
                    raises=interrupted)
    stage.platform.operator = failing
    with pytest.raises(KeyboardInterrupt if interrupted else Refused):
        again(stage).rollback()
    stage.platform.operator = failing.operator
    ended = stage.install.records.get(later)
    assert ended["state"] == "rolled-back", ended
    assert ended["reasonKey"] == ("release-interrupted" if interrupted
                                  else "release-rollback-failed")
    assert stage.link() == stage.tag  # the relink happened before the start
    waiting = stage.install.records.get(stage.tag)
    assert waiting["probePending"] is True and "probeSuperseded" not in waiting, waiting
    assert unprobed_tag(stage.platform.ledger, stage.paths, clock=stage.clock) == stage.tag
    # `recover` ends what the rollback left, and the linked release still waits.
    recovered = again(stage).recover()
    assert recovered["record"] == "rolled-back" and recovered["release"] == stage.tag
    assert stage.install.records.get(stage.tag)["probePending"] is True
    with pytest.raises(Refused, match="nothing-to-recover"):
        again(stage).recover()
    # `verify` runs its probe before any soak moves.
    probes = []
    stage.platform.probe = lambda: probes.append(stage.link()) or True
    moved = again(stage).verify(stage.tag)["verification"]["cutover"]
    assert moved["probe"] == "passed" and moved["state"] == "rehearsing", moved
    assert probes == [stage.tag]
    assert "probePending" not in stage.install.records.get(stage.tag)


def test_a_recover_that_ends_at_a_superseded_release_marks_it_pending(stage, monkeypatch):
    """Review finding (Minor, R18), the error case: a rollback that ends (interrupted)
    before `_pending_again` could run (its ledger write is where the interruption lands)
    still leaves the kept release linked; `recover` then marks it pending wherever the
    links ended."""
    later = superseded_by_a_later_install(stage)
    pending_again = ReleaseInstall._pending_again

    def interrupted(self, folder):
        raise KeyboardInterrupt()

    monkeypatch.setattr(ReleaseInstall, "_pending_again", interrupted)
    with pytest.raises(KeyboardInterrupt):
        again(stage).rollback()
    assert stage.link() == stage.tag
    assert stage.install.records.get(stage.tag)["probeSuperseded"] is True
    assert stage.install.records.get(later)["reasonKey"] == "release-interrupted"
    monkeypatch.setattr(ReleaseInstall, "_pending_again", pending_again)
    assert again(stage).recover()["record"] == "rolled-back"
    waiting = stage.install.records.get(stage.tag)
    assert waiting["probePending"] is True and "probeSuperseded" not in waiting, waiting


def test_an_interrupt_once_the_soak_started_leaves_v2_running_for_the_soak(stage,
                                                                           monkeypatch):
    """Review finding (Minor, R18): an interruption that lands once the soak's start has
    committed never stops the roles `verify` started, since the soak owns them now; v2
    keeps running on the rehearsing record, and `verify` run again changes nothing. An
    interruption before the soak's start (here in the verification's own recording)
    still undoes the starts, as built."""
    installed_while_stopped(stage)
    recording = Cutover.verification_passed

    def interrupted_before(self, run_id, release_tag):
        raise KeyboardInterrupt()

    monkeypatch.setattr(Cutover, "verification_passed", interrupted_before)
    code, result = run_program(["verify"], {"tag": stage.tag}, factory=lambda: again(stage))
    assert (code, result["reason"]) == (130, "release-interrupted")
    assert set(services(stage).values()) == {"stopped"}
    monkeypatch.setattr(Cutover, "verification_passed", recording)
    starting = Cutover.start_soak

    def committed_then_interrupted(self):
        starting(self)
        raise KeyboardInterrupt()

    monkeypatch.setattr(Cutover, "start_soak", committed_then_interrupted)
    code, result = run_program(["verify"], {"tag": stage.tag}, factory=lambda: again(stage))
    assert (code, result["reason"], result["changed"]) == (130, "release-interrupted", True)
    assert result["offered"] == ["docsuri-release verify"]
    assert set(services(stage).values()) == {"running"}, services(stage)
    machine = Cutover(stage.platform.ledger, SYNTHETIC_OPERATIONS, clock=stage.clock)
    assert machine.require()["state"] == "rehearsing" and "soakStartedAt" in machine.require()
    assert "probePending" not in stage.install.records.get(stage.tag)
    monkeypatch.setattr(Cutover, "start_soak", starting)
    with pytest.raises(Refused, match="nothing-to-recover"):
        again(stage).recover()
    moved = again(stage).verify(stage.tag)["verification"]["cutover"]
    assert moved["state"] == "rehearsing" and "soak" not in moved, moved
    assert set(services(stage).values()) == {"running"}


def test_an_interrupt_inside_a_begin_that_committed_offers_recover(stage, monkeypatch):
    """Review finding (Minor, R18): a begin that may have committed counts as touched, so
    an interruption inside it (in production, inside the `docsuri-ledger append`
    subprocess) answers `changed: true` and offers `recover`, which ends the record that
    holds the live exclusion; for an install's begin and for a rollback's."""
    from backend.modules.operations.release_records import ReleaseRecords

    begin = ReleaseRecords.begin

    def committed_then_interrupted(self, *args, **options):
        begin(self, *args, **options)
        raise KeyboardInterrupt()

    monkeypatch.setattr(ReleaseRecords, "begin", committed_then_interrupted)
    code, result = run_program(["install"], {"tag": stage.tag}, factory=lambda: stage.install)
    assert (code, result["reason"], result["changed"]) == (130, "release-interrupted", True)
    assert result["offered"] == ["docsuri-release recover"]
    assert stage.install.records.get(stage.tag)["state"] == "installing"
    assert stage.install.records.exclusion_blocker() == "release-install-active"
    monkeypatch.setattr(ReleaseRecords, "begin", begin)
    recovered = again(stage).recover()
    assert recovered["record"] == "failed" and stage.link() == "v2.0.0", recovered
    assert stage.install.records.exclusion_blocker() is None
    assert set(services(stage).values()) == {"running"}
    assert again(stage).install(stage.tag)["state"] == "installed"
    begin_rollback = ReleaseRecords.begin_rollback

    def rollback_committed_then_interrupted(self, tag):
        begin_rollback(self, tag)
        raise KeyboardInterrupt()

    monkeypatch.setattr(ReleaseRecords, "begin_rollback", rollback_committed_then_interrupted)
    code, result = run_program(["rollback"], {}, factory=lambda: again(stage))
    assert (code, result["changed"], result["offered"]) == (130, True,
                                                            ["docsuri-release recover"])
    assert stage.install.records.get(stage.tag)["state"] == "rolling-back"
    monkeypatch.setattr(ReleaseRecords, "begin_rollback", begin_rollback)
    recovered = again(stage).recover()
    assert recovered["record"] == "installed" and stage.link() == stage.tag, recovered
    assert stage.install.records.exclusion_blocker() is None
    # Before the begin (a refusal at the preflight), nothing changed, as built.
    assert run_program(["install"], {"tag": "v9.9.9"},
                       factory=lambda: again(stage))[1]["changed"] is False
