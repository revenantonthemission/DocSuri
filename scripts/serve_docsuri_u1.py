"""Serve only the owned journey realm with its verified private certificate."""

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
    profile = LocalProfile.load(args.environment_file).journey()
    transport = inspect_transport(profile)
    app = assemble_journey(profile)
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=18039,
        ssl_certfile=str(transport.certificate),
        ssl_keyfile=str(transport.key),
        access_log=False,
        proxy_headers=False,
        limit_concurrency=8,
        timeout_keep_alive=5,
        timeout_graceful_shutdown=10,
    )


if __name__ == "__main__":
    main()
