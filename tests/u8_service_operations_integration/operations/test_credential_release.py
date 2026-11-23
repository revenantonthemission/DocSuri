"""Credential release (U8 plan Step 28; D5, NFR3.2, security-design § 15 "Credential
release (D5)" item 2).

A stand-in keychain (a program under the test's folder that writes one stored password
to standard output, as `docsuri-credential-release` does) releases the realm's operator
stand-in login. The password reaches this process through the pipe only: it is in no
process's arguments or environment and in no file but the keychain's own, and exactly
one connection uses it, after which it is cleared.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from backend.local_profile import private_bytes
from docsuri_ops.u8_platform import credential_release as cr


@pytest.fixture
def password(realm) -> str:
    return json.loads(private_bytes(realm.root / "standin-credentials.json"))["roles"][
        "operator"]


def result_line(login: str, actor: object = "maintainer", *, ok: object = True) -> str:
    """The program's one JSON result on standard error, naming the account sudo
    authenticated, as `docsuri-credential-release` writes it (Step 119)."""
    return json.dumps({"ok": ok, "login": login, "actor": actor}) + "\n"


@pytest.fixture
def keychain(tmp_path, password) -> Path:
    """The stand-in keychain: its one item lives in its own file, as in a keychain."""
    folder = tmp_path / "keychain"
    folder.mkdir(mode=0o700)
    program = folder / "release.py"
    descriptor = os.open(program, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(f"import sys\nsys.stdout.write({password!r} + '\\n')\n"
                     f"sys.stderr.write({result_line('operator')!r})\n")
    return program


class Spawned:
    """`subprocess.Popen`, recording each child's argv and environment."""

    def __init__(self):
        self.children: list[tuple[list[str], dict | None]] = []

    def __call__(self, argv, **options):
        self.children.append((list(argv), options.get("env")))
        return subprocess.Popen(argv, **options)


def files_holding(root: Path, secret: bytes, *, besides: Path) -> list[str]:
    found = []
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink() and path != besides and (
            secret in path.read_bytes()
        ):
            found.append(str(path))
    return found


def test_the_release_command_is_one_fixed_program_and_one_login():
    assert cr.release_command("operator") == [
        "/usr/bin/sudo", "-k", "/Library/DocSuri/release/ops/bin/docsuri-credential-release",
        "operator"]
    with pytest.raises(cr.ReleaseRefused):
        cr.release_command("postgres")
    with pytest.raises(cr.ReleaseRefused):
        cr.release("postgres", command=[sys.executable, "-c", "pass"])


def test_the_released_password_is_used_by_one_connection_and_shows_nowhere(
    tmp_path, realm, keychain, password,
):
    spawned = Spawned()
    released = cr.release("operator", command=[sys.executable, "-I", str(keychain)],
                          popen=spawned)
    assert bytes(released) == password.encode()
    # The child received no password in its arguments, and no environment was set for it.
    [(argv, environment)] = spawned.children
    assert password not in " ".join(argv) and environment is None
    assert "PGPASSWORD" not in os.environ and not any(password in value
                                                      for value in os.environ.values())

    connections = []

    def connect(**options):
        connections.append(sorted(options))
        import psycopg

        return psycopg.connect(**options)

    with cr.one_connection("operator", host="127.0.0.1", port=realm.database_port,
                           dbname="postgres", released=released, connect=connect) as conn:
        assert conn.execute("SELECT current_user").fetchone()[0] == "docsuri_operator"
        # Cleared as soon as the connection holds it.
        assert released == bytearray()
        listing = subprocess.run(["/bin/ps", "-axww", "-o", "args="], capture_output=True,
                                 check=True, timeout=30).stdout
        assert password.encode() not in listing
    assert conn.closed
    assert connections == [["connect_timeout", "dbname", "host", "password", "port",
                            "require_auth", "user"]]
    assert files_holding(tmp_path, password.encode(), besides=keychain) == []
    assert not (Path.home() / ".pgpass").exists() or password.encode() not in (
        Path.home() / ".pgpass").read_bytes()


def test_a_failed_release_is_refused_and_leaves_nothing_behind(tmp_path):
    # L1-36: the refused values are generated per run; 32 hex characters cannot appear in
    # the refusal's message by chance.
    # Each stand-in also writes a valid result line (Step 120(b)), so each case is
    # refused by its own rule, not merely by a missing result.
    result = f"sys.stderr.write({result_line('restore')!r})"
    refused = os.urandom(16).hex()
    with pytest.raises(cr.ReleaseRefused) as caught:
        cr.release("restore", command=[sys.executable, "-I", "-c", "import sys; sys.stdout"
                                       f".write({refused!r}); {result}; sys.exit(3)"])
    assert refused not in str(caught.value)
    with pytest.raises(cr.ReleaseRefused):
        cr.release("restore", command=[sys.executable, "-I", "-c", f"import sys; {result}"])
    long = os.urandom(cr.MAX_PASSWORD).hex()[:cr.MAX_PASSWORD + 5]
    program = tmp_path / "long.py"
    program.write_text(f"import sys\nsys.stdout.write({long!r})\n{result}\n")
    with pytest.raises(cr.ReleaseRefused):
        cr.release("restore", command=[sys.executable, "-I", str(program)])


def test_a_refused_connection_still_clears_the_password(realm):
    released = bytearray(os.urandom(16).hex().encode())  # a wrong password, made per run

    def refusing(**options):
        raise RuntimeError("connection refused")

    with pytest.raises(RuntimeError):
        with cr.one_connection("restore", host="127.0.0.1", port=realm.database_port,
                               dbname="postgres", released=released, connect=refusing):
            pass
    assert released == bytearray()


def test_the_release_answers_the_actor_its_program_named_beside_the_password(tmp_path):
    """Step 120(b) (D4; L2-6): the account sudo authenticated comes back from the
    program's last standard-error line beside the password; a result that does not name
    this login and an account in the login-name form other than `root` is refused, and the
    refusal holds neither the password nor the result's text."""
    password = os.urandom(16).hex()  # generated per run (L1-36)

    def program(name: str, stderr_text: str) -> list[str]:
        path = tmp_path / f"{name}.py"
        path.write_text(f"import sys\nsys.stdout.write({password!r} + '\\n')\n"
                        f"sys.stderr.write({stderr_text!r})\n")
        return [sys.executable, "-I", str(path)]

    sudo_line = "Password:\n"
    released, actor = cr.release_with_actor(
        "operator", command=program("good", sudo_line + result_line("operator")))
    assert bytes(released) == password.encode() and actor == "maintainer"
    assert bytes(cr.release("operator", command=program("alone", result_line("operator")))) == (
        password.encode())

    refused_results = {
        "no-result": "",
        "no-actor": json.dumps({"ok": True, "login": "operator"}) + "\n",
        "root": result_line("operator", "root"),
        "service": result_line("operator", "_docsuri_v2"),
        "outside-form": result_line("operator", "Maintainer Person"),
        "not-ok": result_line("operator", ok=False),
        "another-login": result_line("restore"),
        "not-json": result_line("operator") + "sudo: done\n",
        # More than MAX_RESULT bytes of standard error before a valid last line.
        "too-long": "sudo: " + "x" * cr.MAX_RESULT + "\n" + result_line("operator"),
    }
    for name, text in refused_results.items():
        with pytest.raises(cr.ReleaseRefused) as caught:
            cr.release_with_actor("operator", command=program(name, text))
        message = str(caught.value)
        assert password not in message and (not text.strip() or text.strip() not in message), (
            name)


# --- Step 164(c): the one connection demands SCRAM (NFR3.3; L4-12) -----------------------


def test_the_one_connection_demands_scram():
    """The option's value, and a listener in the instance's place that asks for a
    cleartext password, for MD5 or for nothing: refused before any password is sent, and
    the released bytes are cleared all the same."""
    import psycopg

    from tests.u8_service_operations_integration.component.test_transactions_scram import (
        CLEARTEXT,
        MD5,
        STANDIN_PORT,
        TRUST,
        WeakAuthStandin,
    )
    from tests.u8_service_operations_integration.operations.test_scram_sites import (
        Reached,
        demanded,
        refusing_connect,
    )

    released = bytearray(os.urandom(16).hex().encode())  # made per run (L1-36)
    with pytest.raises(Reached) as reached:
        with cr.one_connection("operator", host="127.0.0.1", port=15432, dbname="docsuri_v2",
                               released=released, connect=refusing_connect):
            pass
    assert demanded(reached.value.options) == (
        "127.0.0.1", 15432, "docsuri_operator", "docsuri_v2", "scram-sha-256")
    assert released == bytearray()
    for request in (CLEARTEXT, MD5, TRUST):
        released = bytearray(os.urandom(16).hex().encode())
        with WeakAuthStandin(request) as standin:
            with pytest.raises(psycopg.OperationalError, match="scram-sha-256"):
                with cr.one_connection("restore", host="127.0.0.1", port=STANDIN_PORT,
                                       dbname="docsuri_v2", released=released):
                    pass
        assert standin.passwords_seen == 0, request
        assert released == bytearray(), request
