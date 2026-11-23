"""U2's coverage phase in U2's CI lane (U8 plan Step 44; your decision of 2026-10-25, "Run
it in U2's CI lane").

`.github/workflows/u2-account-controls.yml` runs `scripts/verify_docsuri_u2.py --phase
coverage` on a fresh environment after its five owner layers, so a U2 figure below 80.00%
fails the lane, as U4's and U5's already do. This reads the workflow as it is checked in.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "u2-account-controls.yml"
LAYERS = ["database", "repository", "component", "integration", "operations"]
TOOL = "scripts/verify_docsuri_u2.py"


def jobs() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())["jobs"]


def phases(job: dict) -> list[str]:
    """Each step's U2 phase, in order, from its `--phase <name>` argument."""
    found = []
    for step in job["steps"]:
        words = " ".join(str(step.get("run", "")).split()).split()
        if TOOL in words and "--phase" in words:
            found.append(words[words.index("--phase") + 1])
    return found


def test_the_five_owner_layers_still_run_and_none_measures_coverage():
    owners = jobs()["owners"]
    assert owners["strategy"]["matrix"]["phase"] == LAYERS
    found = phases(owners)
    assert found[:2] == ["setup", "migrate"] and len(found) == 3 and "coverage" not in found
    assert any("${{ matrix.phase }}" in str(step.get("run", "")) for step in owners["steps"])


def test_the_coverage_phase_runs_after_the_five_layers_on_a_fresh_environment():
    coverage = jobs()["coverage"]
    # After the five layers: the job waits for every owner layer's job.
    assert coverage["needs"] == ["owners"]
    # On a fresh environment of its own: setup, then migrate, then coverage.
    assert phases(coverage) == ["setup", "migrate", "coverage"]
    run = next(step["run"] for step in coverage["steps"] if "--phase coverage" in
               " ".join(str(step.get("run", "")).split()))
    assert "--profile synthetic-local" in " ".join(run.split())
    assert "$DOCSURI_U2_ENVIRONMENT_FILE" in run
    assert coverage["env"]["DOCSURI_U2_ENVIRONMENT_FILE"] == "/tmp/docsuri-u2-run/environment.json"


def test_the_lane_keeps_its_settings_and_its_existing_job_names():
    value = yaml.safe_load(WORKFLOW.read_text())
    assert value["permissions"] == {"contents": "read"}
    assert set(value["jobs"]) == {"frontend", "owners", "coverage"}
    # No step continues past a failure, so a figure below the floor fails the lane.
    for job in value["jobs"].values():
        assert all(not step.get("continue-on-error") for step in job["steps"])
