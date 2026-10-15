"""Serve the owned U2 realm with its verified private certificate.

The caller owns process supervision, resource enforcement and finite experiment
duration. This executable never starts background workers or mutates trust stores.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ops/src"))

import uvicorn
from docsuri_ops.local_transport import inspect_transport

from backend.local_host import assemble_journey
from backend.local_profile import LocalProfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment-file", type=Path, required=True)
    args = parser.parse_args()
    profile = LocalProfile.load(args.environment_file)
    if profile.realm != "account-controls" or profile.database_name != "docsuri_u2":
        raise ValueError("U2 server requires the owned account-controls realm")
    transport = inspect_transport(profile)
    app = assemble_journey(profile)
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=18049,
        workers=1,
        ssl_certfile=str(transport.certificate),
        ssl_keyfile=str(transport.key),
        access_log=False,
        proxy_headers=False,
        # HTTP admission is separately split 8 normal + 2 recovery. The socket
        # cap includes keep-alive connections and must not consume that reserve.
        limit_concurrency=32,
        backlog=16,
        timeout_keep_alive=5,
        timeout_graceful_shutdown=10,
    )


if __name__ == "__main__":
    main()
