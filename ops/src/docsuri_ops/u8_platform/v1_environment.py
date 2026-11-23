"""The synthetic v1's environment: the only addresses v1's code may run with in the
composed realm (U8 plan Step 43; decision "The composed realm's addresses").

v1's own code defaults to v1's real stores: its session store to `localhost:6379` (the
live site's Redis), its database, search index, object store and web to their usual
ports. In the realm every process that runs v1's code (`scripts/u8_synthetic_v1.py`'s
API and web, and the realm driver's `platform.v1.lifecycle.apply`) is given exactly the
environment `u8_synthetic_v1.wire_driver` wrote, and this module refuses it unless:

- the file is a private regular file (0600, one link, never a link, owned by this user)
  in the realm's run root;
- it names v1's database, Redis, search index and object store, each on 127.0.0.1 at the
  realm's own stand-in port (15510, 16389, 19209, 19009);
- no value anywhere in it names any other host or port: in particular not v1's real ones
  (6379, 5432, 9200, 9000, 3000, 8000);
- it carries no alternate route to a store (`DB_HOST`, `AWS_ENDPOINT_URL`, `REDIS_URL`).

Anything else fails closed with a fixed reason, before any v1 code starts.
"""

from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path
from urllib.parse import urlsplit

REALM_RUN = Path("/tmp/docsuri-u8-run").resolve()
LOOPBACK = "127.0.0.1"
POSTGRES_PORT, REDIS_PORT, SEARCH_PORT, OBJECTS_PORT = 15510, 16389, 19209, 19009
API_PORT, WEB_PORT, PUBLIC_PORT = 18112, 18113, 18110
REALM_PORTS = frozenset({POSTGRES_PORT, REDIS_PORT, SEARCH_PORT, OBJECTS_PORT, API_PORT,
                         WEB_PORT, PUBLIC_PORT})
# v1's real addresses, which nothing in the realm may reach.
V1_REAL_PORTS = frozenset({6379, 5432, 9200, 9000, 9001, 3000, 8000, 9324})
REQUIRED = {
    "DATABASE_URL": POSTGRES_PORT,
    "DOCSURI_OPENSEARCH_ENDPOINT": SEARCH_PORT,
    "AWS_ENDPOINT_URL_S3": OBJECTS_PORT,
}
FORBIDDEN_KEYS = frozenset({"DB_HOST", "DB_PORT", "AWS_ENDPOINT_URL", "REDIS_URL",
                            "AWS_ENDPOINT_URL_SQS", "DOCSURI_EMBEDDING_API_BASE",
                            "DOCSURI_LLM_API_BASE", "DOCSURI_BEDROCK_MODEL_ID",
                            "RESEND_API_KEY", "EMAIL_PROVIDER"})
_URL = re.compile(r"[a-z][a-z0-9+.-]*://[^\s,]+", re.IGNORECASE)
MAX_BYTES = 16 * 1024


class V1EnvironmentRefused(ValueError):
    """A fixed reason; never a value from the file."""


def _port_of(url: str) -> tuple[str | None, int | None]:
    parts = urlsplit(url)
    try:
        return parts.hostname, parts.port
    except ValueError:
        raise V1EnvironmentRefused("v1-environment-address-unreadable") from None


def require_realm_environment(environment: dict) -> dict:
    """The environment itself: required stores at the realm's ports, nothing else."""
    if not isinstance(environment, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in environment.items()
    ):
        raise V1EnvironmentRefused("v1-environment-shape-refused")
    if FORBIDDEN_KEYS & set(environment):
        raise V1EnvironmentRefused("v1-environment-alternate-route-refused")
    if environment.get("REDIS_HOST") != LOOPBACK or environment.get("REDIS_PORT") != str(
        REDIS_PORT
    ):
        raise V1EnvironmentRefused("v1-environment-redis-not-realm")
    for key, port in REQUIRED.items():
        value = environment.get(key)
        if not value:
            raise V1EnvironmentRefused("v1-environment-store-missing")
        host, found = _port_of(value)
        if host != LOOPBACK or found != port:
            raise V1EnvironmentRefused("v1-environment-store-not-realm")
    if not environment["DATABASE_URL"].startswith(("postgresql://", "postgresql+psycopg://")):
        raise V1EnvironmentRefused("v1-environment-store-not-realm")
    for key, value in environment.items():
        for url in _URL.findall(value):
            host, port = _port_of(url)
            if host != LOOPBACK or port is None or port not in REALM_PORTS:
                raise V1EnvironmentRefused("v1-environment-address-not-realm")
        if key.endswith("PORT") and (not value.isdigit() or int(value) not in REALM_PORTS):
            raise V1EnvironmentRefused("v1-environment-address-not-realm")
        if key.endswith("HOST") and value != LOOPBACK:
            raise V1EnvironmentRefused("v1-environment-address-not-realm")
    return dict(environment)


SOURCE_ROOTS = ("", "shared/python/src", "backend/modules/discovery/src",
                "backend/modules/summarization/src", "ops/src")


def runtime_environment(environment: dict, checkout: Path) -> dict:
    """A v1 process's whole environment: the checked addresses, the source roots of v1's
    fixed checkout, and nothing inherited beyond the path, home and locale."""
    checked = require_realm_environment(environment)
    base = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "TMPDIR")
            if key in os.environ}
    base["PYTHONPATH"] = os.pathsep.join(str(Path(checkout) / part) for part in SOURCE_ROOTS)
    return {**base, **checked}


def load(path: Path | str | None, *, run_root: Path = REALM_RUN) -> dict:
    """The file `wire_driver` wrote, checked; refused if missing or anything differs."""
    if not path:
        raise V1EnvironmentRefused("v1-environment-unconfigured")
    target = Path(path)
    root = Path(run_root).resolve()
    if target.parent.resolve() != root / "v1" or target.name != "environment.json":
        raise V1EnvironmentRefused("v1-environment-outside-the-run")
    try:
        descriptor = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        raise V1EnvironmentRefused("v1-environment-missing") from None
    except OSError:
        raise V1EnvironmentRefused("v1-environment-unreadable") from None
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
            raise V1EnvironmentRefused("v1-environment-custody-differs")
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise V1EnvironmentRefused("v1-environment-too-large")
    try:
        value = json.loads(raw)
    except ValueError:
        raise V1EnvironmentRefused("v1-environment-unreadable") from None
    return require_realm_environment(value)
