"""Owned U5 HTTPS host, run only under the bounded scoped supervisor."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ops/src"))

import uvicorn
from docsuri_ops.local_transport import inspect_transport

from backend.local_profile import LocalProfile


def assemble(environment_file: Path):
    profile = LocalProfile.load(environment_file)
    if profile.realm != "topics-digests" or profile.database_name != "docsuri_u5":
        raise ValueError("U5 server requires its owned topics-digests realm")
    from backend.u5_host import assemble_u5

    transport = inspect_transport(profile)
    app = assemble_u5(profile)
    if app.state.profile.run_id != profile.run_id:
        raise ValueError("U5 assembly identity mismatch")
    return app, transport


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment-file", required=True, type=Path)
    args = parser.parse_args()
    app, transport = assemble(args.environment_file)
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=18089,
        workers=1,
        ssl_certfile=str(transport.certificate),
        ssl_keyfile=str(transport.key),
        access_log=False,
        proxy_headers=False,
        limit_concurrency=32,
        backlog=16,
        timeout_keep_alive=5,
        timeout_graceful_shutdown=10,
    )


if __name__ == "__main__":
    main()
