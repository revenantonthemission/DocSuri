"""The first v2 release's guard (U8 plan Step 44; cicd-pipeline § 4, step 3).

    python3 scripts/u8_release_guard.py --previous-v2-tags <count> --created <tag>

`release.yml` lists `origin`'s `v2.*` tags before tagging, and passes `custom_tag: 2.0.0`
when there are none. This guard then fails the job when no `v2.*` tag existed before the
run and the created tag is not `v2.0.0`, so a wrong first version is never published.
With an earlier `v2.*` tag, any created `v2.*` tag passes, and an empty one (no release
this run) passes too. It uses only the standard library: the release job runs it with
the runner's own Python, before any dependency is installed.

One JSON line is printed; the exit code is 1 when the guard fails.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

FIRST = "v2.0.0"
V2 = re.compile(r"v2\.\d+\.\d+")


def verdict(previous_v2_tags: int, created: str) -> str | None:
    """The reason the created tag is refused, or None when it may be published."""
    if previous_v2_tags < 0:
        return "previous-count-invalid"
    if not created:
        return None  # no release this run: nothing is published
    if not V2.fullmatch(created):
        return "created-tag-not-v2"
    if previous_v2_tags == 0 and created != FIRST:
        return "first-v2-release-not-v2.0.0"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="u8_release_guard.py")
    parser.add_argument("--previous-v2-tags", required=True, type=int)
    parser.add_argument("--created", required=True)
    args = parser.parse_args(argv)
    reason = verdict(args.previous_v2_tags, args.created.strip())
    print(json.dumps({"created": args.created.strip(), "previousV2Tags": args.previous_v2_tags,
                      "passed": reason is None, "reason": reason}))
    return 0 if reason is None else 1


if __name__ == "__main__":
    sys.exit(main())
