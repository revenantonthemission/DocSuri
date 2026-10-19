"""Owned U5 HTTPS host, run only under the bounded scoped supervisor.

`--real-delivery` is the operator-only real composition (backend/u5_real_delivery.py):
it reads the realm's private `real-delivery.json` plus `EMAIL_PROVIDER` and
`RESEND_API_KEY` from this process environment, and refuses to start when any of
them is missing or invalid. Without the flag the host is synthetic and never
reads provider configuration, even if those variables are present.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ops/src"))

import uvicorn
from docsuri_ops.local_transport import inspect_transport

from backend.local_profile import LocalProfile


def assemble(environment_file: Path, *, real_delivery: bool = False):
    profile = LocalProfile.load(environment_file)
    if profile.realm != "topics-digests" or profile.database_name != "docsuri_u5":
        raise ValueError("U5 server requires its owned topics-digests realm")
    transport = inspect_transport(profile)
    if real_delivery:
        from backend.u5_real_delivery import assemble_u5_real, load_activation

        app = assemble_u5_real(profile, load_activation(profile))
    else:
        from backend.u5_host import assemble_u5

        app = assemble_u5(profile)
    if app.state.profile.run_id != profile.run_id:
        raise ValueError("U5 assembly identity mismatch")
    return app, transport


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment-file", required=True, type=Path)
    parser.add_argument("--real-delivery", action="store_true")
    args = parser.parse_args()
    app, transport = assemble(args.environment_file, real_delivery=args.real_delivery)
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
