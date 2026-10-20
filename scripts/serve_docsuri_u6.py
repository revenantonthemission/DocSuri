"""Owned U6 HTTPS host on 127.0.0.1:18099 with the environment's TLS.

Without a flag the host is synthetic: `assemble_u6`, over the fake Notion, which also
refuses an environment holding the operator's `real-export.json`. `--real-export` is
the operator-only real composition (`backend/u6_real_export.py`, cicd-pipeline §5): it
reads the environment's private `real-export.json`, refuses any gap with
POLICY_UNRESOLVED and refuses an environment that holds any evidence file. The
environment tool's bounded `serve` phase never passes `--real-export`.
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

REALM = "approved-export"
DATABASE = "docsuri_u6"
PORT = 18099


def compose(profile: LocalProfile, *, real_export: bool = False):
    """The application for this owned realm: synthetic, or the operator's real one."""
    if profile.realm != REALM or profile.database_name != DATABASE:
        raise ValueError("U6 server requires its owned approved-export realm")
    if real_export:
        from backend.u6_real_export import assemble_u6_real, load_activation

        app = assemble_u6_real(profile, load_activation(profile))
    else:
        from backend.u6_host import assemble_u6

        app = assemble_u6(profile)
    if app.state.profile.run_id != profile.run_id:
        raise ValueError("U6 assembly identity mismatch")
    return app


def assemble(environment_file: Path, *, real_export: bool = False):
    profile = LocalProfile.load(environment_file)
    app = compose(profile, real_export=real_export)
    return app, inspect_transport(profile)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment-file", required=True, type=Path)
    parser.add_argument("--real-export", action="store_true")
    args = parser.parse_args()
    app, transport = assemble(args.environment_file, real_export=args.real_export)
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=PORT,
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
