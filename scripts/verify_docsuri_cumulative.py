"""Cumulative U1/U7/U2 completion check; runs only at its recorded human decision.

Composes the three owned runners' verification phases and the cumulative frontend
configuration against already-provisioned synthetic realms. A missing or expired
realm is a failed prerequisite: this check never provisions, never reseeds and
never converts an unavailable layer into a pass. It does not claim fixture-only
provider or public parity.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "backend/.venv/bin/python"
PHASE_TIMEOUT_SECONDS = 1800

LAYERS = (
    {
        "unit": "u1",
        "runner": "scripts/verify_docsuri_u1.py",
        "environment": Path("/tmp/docsuri-u1-run/environment.json"),
        # "contracts" is excluded: U1 never authored tests/u1_integrated_paper_journey/contracts
        # (U1's code-summary records its contracts tests as not authored in that unit).
        # "model" is excluded: U1's code-summary records model quality as blocked by the
        # unresolved P1/P2 grounding evidence (the phase refuses with ModelUnavailable:
        # runtime version or cloud-disable evidence mismatch).
        "phases": (
            "database",
            "repository",
            "component",
            "integration",
            "operations",
        ),
    },
    {
        "unit": "u2",
        "runner": "scripts/verify_docsuri_u2.py",
        "environment": Path("/tmp/docsuri-u2-run/environment.json"),
        "phases": ("database", "repository", "component", "integration", "operations"),
    },
    {
        # U3 extends the same application; its layer runs after U2 so the
        # cumulative composition covers the corpus/discovery/assistance owners.
        # The browser phase stays with U3's own runner evidence; this check
        # never claims fixture-only provider or public parity.
        "unit": "u3",
        "runner": "scripts/verify_docsuri_u3.py",
        "environment": Path("/tmp/docsuri-u3-run/environment.json"),
        "phases": ("database", "repository", "component", "integration", "operations"),
    },
    {
        "unit": "u7",
        "runner": "scripts/verify_docsuri_u7.py",
        "environment": Path("/tmp/docsuri-u7-run/environment.json"),
        "phases": ("component", "database", "repository", "integration", "operations"),
    },
)

FRONTEND_CUMULATIVE = (
    "corepack",
    "pnpm@9.15.9",
    "--dir",
    "frontend",
    "exec",
    "vitest",
    "run",
    "--config",
    "vitest.u2-cumulative.config.ts",
)


def layer_state(path: Path) -> str:
    """A layer is runnable only within its recorded, unexpired synthetic window."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return "prerequisite-missing"
    if path.is_symlink() or not (info.st_mode & 0o400):
        return "prerequisite-invalid"
    value = json.loads(path.read_text())
    if not isinstance(value.get("expiresAt"), (int, float)) or value["expiresAt"] <= time.time():
        return "prerequisite-expired"
    return "runnable"


def command_for(layer: dict, phase: str) -> list[str]:
    return [
        str(PYTHON),
        str(ROOT / layer["runner"]),
        "--phase",
        phase,
        "--profile",
        "synthetic-local",
        "--environment-file",
        str(layer["environment"]),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-recorded-decision",
        action="store_true",
        help="acknowledge that this exact invocation is the recorded human-approved cumulative check",
    )
    args = parser.parse_args()
    if not args.confirm_recorded_decision:
        print(
            "refused: the cumulative check runs only at its recorded human decision point",
            file=sys.stderr,
        )
        return 2
    evidence: list[dict] = []
    failed = False
    for layer in LAYERS:
        state = layer_state(layer["environment"])
        entry = {"unit": layer["unit"], "state": state, "phases": []}
        if state == "runnable":
            for phase in layer["phases"]:
                command = command_for(layer, phase)
                try:
                    result = subprocess.run(
                        command,
                        cwd=ROOT,
                        capture_output=True,
                        text=True,
                        timeout=PHASE_TIMEOUT_SECONDS,
                    )
                    outcome = {
                        "phase": phase,
                        "exitCode": result.returncode,
                        "stdoutTail": result.stdout.strip().splitlines()[-1:] or [],
                    }
                except subprocess.TimeoutExpired:
                    outcome = {"phase": phase, "exitCode": None, "failure": "phase-timeout"}
                entry["phases"].append(outcome)
                if outcome["exitCode"] != 0:
                    failed = True
                    break
        elif state != "runnable":
            # The layer's own setup phase provisions a fresh realm; the
            # cumulative check never does so on the person's behalf.
            failed = True
        evidence.append(entry)
    if not failed:
        result = subprocess.run(
            list(FRONTEND_CUMULATIVE),
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=PHASE_TIMEOUT_SECONDS,
        )
        evidence.append(
            {
                "unit": "frontend-cumulative",
                "exitCode": result.returncode,
                "stdoutTail": result.stdout.strip().splitlines()[-3:] or [],
            }
        )
        if result.returncode != 0:
            failed = True
    print(json.dumps({"cumulative": evidence, "passed": not failed}, indent=1, ensure_ascii=False))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
