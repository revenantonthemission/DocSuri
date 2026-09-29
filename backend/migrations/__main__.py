"""Explicit readonly CLI. Mutation belongs to the protected REM-1 runner."""

import argparse
import json
import os
from dataclasses import asdict

from . import inspect_migrations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True)
    parser.parse_args()
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print(json.dumps({"state": "UNAVAILABLE", "reason": "database_not_configured"}))
        return 2
    try:
        result = inspect_migrations(dsn)
    except Exception:
        print(json.dumps({"state": "UNAVAILABLE", "reason": "inspection_failed"}))
        return 2
    print(json.dumps(asdict(result)))
    return 0 if result.state == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
