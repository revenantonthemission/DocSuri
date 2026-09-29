#!/usr/bin/env python3
"""Reduce a retained Grype report to reviewable occurrence/advisory facts, never suppressions."""

import argparse
import collections
import json
from pathlib import Path

from scan_sbom import classify_report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--details", action="store_true")
    args = parser.parse_args()
    report = json.loads(args.report.read_bytes())
    summary = classify_report(report)
    matches = report["matches"] + report.get("ignoredMatches", [])
    blocking = [item for item in matches
                if item["vulnerability"].get("severity") not in {"Negligible", "Low", "Medium"}]
    packages = collections.Counter(
        (item["artifact"]["name"], item["artifact"]["version"]) for item in blocking
    )
    summary["packages"] = [
        {"name": name, "version": version, "count": count}
        for (name, version), count in packages.most_common()
    ]
    summary["fixStates"] = dict(collections.Counter(
        item["vulnerability"].get("fix", {}).get("state", "unknown") for item in blocking
    ))
    summary["severityCounts"] = dict(collections.Counter(
        item["vulnerability"].get("severity", "Unknown") for item in matches
    ))
    if args.details:
        summary["findingsDetail"] = [
            {"id": item["vulnerability"]["id"],
             "severity": item["vulnerability"].get("severity", "Unknown"),
             "package": item["artifact"]["name"], "version": item["artifact"]["version"],
             "locations": item["artifact"].get("locations", []),
             "fix": item["vulnerability"].get("fix"),
             "namespace": item["vulnerability"].get("namespace")}
            for item in blocking
        ]
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
