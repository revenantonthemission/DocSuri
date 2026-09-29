"""Run frozen local checks from an isolated reviewed checkout; no production services touched."""

import argparse
import json
import os
import subprocess
from pathlib import Path

PROJECTS = (
    "shared/python",
    "platform_integrity",
    "backend",
    "ingestion",
    "ops",
    "backend/modules/discovery",
    "backend/modules/summarization",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--profile", choices=("pr", "release"), default="pr")
    args = parser.parse_args()
    root = args.root.resolve()
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if actual != args.revision or (root / "backend/.env").exists():
        raise SystemExit("requires exact reviewed revision and credential-free checkout")
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(Path.home()),
        "LANG": "en_US.UTF-8",
        "AWS_EC2_METADATA_DISABLED": "true",
        "AWS_CONFIG_FILE": "/dev/null",
        "AWS_SHARED_CREDENTIALS_FILE": "/dev/null",
        "R1_TEST_PROFILE": args.profile,
        "NEXT_TELEMETRY_DISABLED": "1",
        "CI": "1",
    }
    results = []
    for project in PROJECTS:
        cmd = [
            "uv",
            "run",
            "--frozen",
            "--all-extras",
            "pytest",
            "--hypothesis-seed=20260924",
            "-ra",
        ]
        run = subprocess.run(cmd, cwd=root / project, env=env, timeout=900, check=False)
        results.append({"project": project, "returncode": run.returncode})
        if run.returncode:
            break
    print(json.dumps({"revision": actual, "profile": args.profile, "results": results}))
    return 1 if any(r["returncode"] for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
