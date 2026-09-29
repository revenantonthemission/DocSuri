#!/usr/bin/env python3
"""Bounded, verify-only Syft/Grype capture. Reports retain failures and never install packages."""

import argparse
import hashlib
import json
import os
import selectors
import shutil
import signal
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

BINARIES = {
    "syft": "17e4215af72264e186a843269d0b797697d643f53841d9598f73614bbcbe9022",
    "grype": "f8486425f232aea78fc932249ca0923672d88be36c9661e25e82ea1fa8cd0cae",
}


def classify_report(report):
    """Keep suppressed/unknown findings visible; a capture is not a release approval."""
    if not isinstance(report, dict):
        raise ValueError("invalid scanner report")
    descriptor = report.get("descriptor", {})
    if (
        descriptor.get("name") != "grype" or descriptor.get("version") != "0.119.0"
        or descriptor.get("db", {}).get("status", {}).get("valid") is not True
    ):
        raise ValueError("unverified scanner or database")
    config = descriptor.get("configuration", {})
    if any(config.get(key) for key in ("only-fixed", "only-notfixed", "ignore-wontfix", "exclude")):
        raise ValueError("filtered scanner coverage")
    matches, ignored = report.get("matches"), report.get("ignoredMatches", [])
    if not isinstance(matches, list) or not isinstance(ignored, list):
        raise ValueError("scanner findings missing")
    high = unknown = 0
    for item in [*matches, *ignored]:
        if not isinstance(item, dict):
            raise ValueError("invalid scanner finding")
        vulnerability, artifact = item.get("vulnerability", {}), item.get("artifact", {})
        if not vulnerability.get("id") or not artifact.get("id"):
            raise ValueError("unbound scanner finding")
        severity = vulnerability.get("severity")
        high += severity in {"High", "Critical"}
        unknown += severity not in {"Negligible", "Low", "Medium", "High", "Critical"}
    reasons = ["role_closure_and_trusted_freshness_acceptance_required"]
    if high:
        reasons.append("unapproved_high_or_critical_findings")
    if unknown:
        reasons.append("severity_unknown")
    if ignored:
        reasons.append("scanner_suppressions_require_explicit_review")
    state = "BLOCKED" if high else "INCOMPLETE" if unknown or ignored else "SCANNED"
    return {"state": state, "findings": len(matches) + len(ignored),
            "blockingFindings": high + unknown, "ignoredFindings": len(ignored),
            "reasons": reasons}


def run(command, environment, output, timeout):
    import psutil

    with output.open("xb") as stream, output.with_suffix(".stderr.log").open("xb") as errors:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL, start_new_session=True, env=environment,
        )
        deadline = time.monotonic() + timeout
        total = {"stdout": 0, "stderr": 0}
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ, ("stdout", stream))
                selector.register(process.stderr, selectors.EVENT_READ, ("stderr", errors))
                while selector.get_map():
                    if (
                        time.monotonic() >= deadline
                        or shutil.disk_usage(output.parent).free < 10 * 1024**3
                    ):
                        raise RuntimeError("scanner deadline or disk reserve exhausted")
                    try:
                        parent = psutil.Process(process.pid)
                        family = [parent, *parent.children(recursive=True)]
                        rss = sum(item.memory_info().rss for item in family)
                        if rss > 2 * 1024**3:
                            raise RuntimeError("scanner RSS limit exceeded")
                    except psutil.NoSuchProcess:
                        pass
                    for key, _ in selector.select(.1):
                        channel, destination = key.data
                        data = os.read(key.fileobj.fileno(), 65536)
                        if not data:
                            selector.unregister(key.fileobj)
                            continue
                        total[channel] += len(data)
                        if total[channel] > 64 * 1024**2:
                            raise RuntimeError("scanner report limit exceeded")
                        destination.write(data)
            return process.wait(timeout=max(.1, deadline - time.monotonic()))
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=2)
            process.stdout.close()
            process.stderr.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tools", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--source", required=True, help="Explicit dir:/docker:/registry: target")
    parser.add_argument("--profile", required=True)
    args = parser.parse_args()
    for name, expected in BINARIES.items():
        path = args.tools / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError("scanner binary integrity mismatch")
    args.output.mkdir(parents=True, mode=0o700, exist_ok=False)
    environment = {
        "PATH": os.environ.get("PATH", ""), "HOME": str(args.output), "LANG": "en_US.UTF-8",
        "SYFT_CHECK_FOR_APP_UPDATE": "false", "GRYPE_CHECK_FOR_APP_UPDATE": "false",
        "GRYPE_DB_CACHE_DIR": str(args.tools / "grype-db"),
        "GRYPE_DB_AUTO_UPDATE": "false",
        "GRYPE_DB_MAX_ALLOWED_BUILT_AGE": "24h",
    }
    if args.source.startswith("docker:"):
        environment["DOCKER_HOST"] = subprocess.run(
            ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip()
    sbom = args.output / "sbom.cdx.json"
    scan = args.output / "grype.json"
    summary = {"subject": args.subject, "source": args.source, "profile": args.profile,
               "observedAt": datetime.now(UTC).isoformat(), "timeQuality": "host-unverified",
               "scannerBinaries": BINARIES, "state": "INCOMPLETE", "reasons": []}
    try:
        rc = run(
            [str(args.tools / "syft"), args.source, "-o", "cyclonedx-json"], environment, sbom, 600,
        )
        summary["syftReturnCode"] = rc
        if rc != 0:
            raise RuntimeError("SBOM command failed")
        document = json.loads(sbom.read_bytes())
        if rc != 0 or document.get("bomFormat") != "CycloneDX" or not document.get("components"):
            raise RuntimeError("SBOM capture incomplete")
        summary["componentCount"] = len(document["components"])
        summary["sbomSha256"] = hashlib.sha256(sbom.read_bytes()).hexdigest()
        rc = run(
            [str(args.tools / "grype"), "sbom:" + str(sbom), "-o", "json"], environment, scan, 900,
        )
        summary["grypeReturnCode"] = rc
        if rc != 0:
            raise RuntimeError("vulnerability scanner command failed")
        report = json.loads(scan.read_bytes())
        summary["reportSha256"] = hashlib.sha256(scan.read_bytes()).hexdigest()
        summary.update(classify_report(report))
        summary["scannerDescriptor"] = report["descriptor"]
    except Exception as error:
        summary["reasons"] = [type(error).__name__, "scanner_capture_incomplete"]
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    display = {key: value for key, value in summary.items() if key != "scannerDescriptor"}
    print(json.dumps(display, indent=2))
    return 0 if summary["state"] == "SCANNED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
