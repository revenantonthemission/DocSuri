"""Provision only the explicit owned synthetic journey HTTPS material."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ops/src"))

from docsuri_ops.local_transport import prepare_transport

from backend.local_profile import LocalProfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment-file", type=Path, required=True)
    args = parser.parse_args()
    profile = LocalProfile.load(args.environment_file).journey()
    transport = prepare_transport(profile)
    print(
        json.dumps(
            {
                "origin": profile.origin,
                "certificateSha256": transport.certificate_sha256,
                "trustStoreModified": False,
            }
        )
    )


if __name__ == "__main__":
    main()
