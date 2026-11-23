"""Credential release (U8 plan Step 27; D5, NFR3.2, security-design § 5.4).

The operator tool's logins in v2's instance live in the System keychain. For one bound
operation the tool opens a pipe to `docsuri-credential-release <login>` (in person, as
root through `sudo -k`), reads the password from it, and passes it to exactly one
connection as a libpq parameter. It never sets `PGPASSWORD`, never writes a password
file and never puts the password in a process's arguments; the password is dropped
once the operation's connection closes.

The program also writes one JSON result to standard error, naming the account sudo
authenticated (U8 plan Step 119; D4): `release_with_actor` reads it beside the password,
and every release refuses a result that does not name this login and an account in the
login-name form other than `root`.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable, Iterator
from contextlib import contextmanager

PROGRAM = "/Library/DocSuri/release/ops/bin/docsuri-credential-release"
# `platform` is the operator tool's PlatformControl store login in production (decision
# "PlatformControl's store in production"), released in person like the other two.
LOGINS = ("operator", "restore", "platform")
LOGIN_USERS = {"operator": "docsuri_operator", "restore": "docsuri_restore",
               "platform": "docsuri_platform_operator"}
MAX_PASSWORD = 256
MAX_RESULT = 4096
RELEASE_SECONDS = 120
# The login-name form (as `drivers/arrangement.py`'s `LOGIN_NAME`), which already refuses
# a name beginning with `_`.
LOGIN_NAME = re.compile(r"[a-z][a-z0-9_.-]{0,31}")


class ReleaseRefused(RuntimeError):
    """The credential could not be released; the message never holds the password."""


def release_command(login: str) -> list[str]:
    if login not in LOGINS:
        raise ReleaseRefused("login outside the closed set")
    return ["/usr/bin/sudo", "-k", PROGRAM, login]


def _result_actor(login: str, result: bytes) -> str | None:
    """The account the program's last standard-error line names, or None when that line
    is not its result for this login (sudo's own lines before it are dropped)."""
    if len(result) > MAX_RESULT:
        return None
    lines = result.decode("utf-8", errors="replace").strip().splitlines()
    try:
        value = json.loads(lines[-1]) if lines else None
    except ValueError:
        return None
    if not isinstance(value, dict) or value.get("ok") is not True or value.get(
            "login") != login:
        return None
    actor = value.get("actor")
    if not isinstance(actor, str) or LOGIN_NAME.fullmatch(actor) is None or actor == "root":
        return None
    return actor


def release_with_actor(login: str, *, command: list[str] | None = None,
                       popen: Callable = subprocess.Popen) -> tuple[bytearray, str]:
    """Read one login's password from the release program's standard output, a pipe
    this process opened, and the account sudo authenticated from its result on standard
    error. The caller receives the password as a mutable buffer it can clear."""
    argv = command or release_command(login)
    if login not in LOGINS:
        raise ReleaseRefused("login outside the closed set")
    child = popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=None)
    try:
        raw = bytearray(child.stdout.read(MAX_PASSWORD + 2))
        result = child.stderr.read(MAX_RESULT + 1)
        status = child.wait(timeout=RELEASE_SECONDS)
    finally:
        child.stdout.close()
        child.stderr.close()
    actor = _result_actor(login, result)
    if status != 0 or not raw or len(raw) > MAX_PASSWORD + 1 or actor is None:
        raw[:] = b"\0" * len(raw)
        raise ReleaseRefused("the credential was not released")
    if raw.endswith(b"\n"):
        del raw[-1]
    return raw, actor


def release(login: str, **options) -> bytearray:
    """One login's password alone (`release_with_actor`'s first answer), so every release
    reads the program's result."""
    return release_with_actor(login, **options)[0]


@contextmanager
def one_connection(login: str, *, host: str, port: int, dbname: str,
                   released: bytearray | None = None, connect: Callable | None = None,
                   **release_options) -> Iterator[object]:
    """One connection for one bound operation: the password is a libpq parameter of
    this connection only, and is cleared when the connection closes."""
    import psycopg

    secret = released if released is not None else release(login, **release_options)
    try:
        connection = (connect or psycopg.connect)(
            host=host, port=port, dbname=dbname, user=LOGIN_USERS[login],
            password=secret.decode(), require_auth="scram-sha-256", connect_timeout=5,
        )
    finally:
        secret[:] = b"\0" * len(secret)
        secret.clear()
    try:
        yield connection
    finally:
        connection.close()
