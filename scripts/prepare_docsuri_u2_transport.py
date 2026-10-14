"""Provision only the explicit owned U2 HTTPS material, without global trust."""

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
    profile = LocalProfile.load(args.environment_file)
    if profile.realm != "account-controls" or profile.database_name != "docsuri_u2":
        raise ValueError("U2 transport requires the owned account-controls realm")
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
