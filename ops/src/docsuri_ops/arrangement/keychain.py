"""The arrangement's secrets (U8 plan Step 37; D5, D8, security-design § 5.4, § 6.1).

Every production password and secret is generated at installation by root from 32
random bytes (`generate`, hexadecimal) and written straight into its holder: a file of the
holder's account at 0600 (`write_secret_file`), or a generic-password item in the
System keychain (`store_login`) for the operator tool's logins and the backup volume's
passphrase. Nothing here returns a secret to a caller that would log it, and the
installation log records only that a step ran.
"""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

from . import safe_fs

# The operator tool's logins, released in person (`docsuri-credential-release`, D5).
LOGIN_ITEMS = {"operator": "docsuri-v2-operator", "restore": "docsuri-v2-restore",
               "platform": "docsuri-v2-platform"}
VOLUME_ITEM = "DocSuri_Backup"
KEYCHAIN_ACCOUNT = "root"
SECRET_BYTES = 32


def generate() -> bytes:
    """A fresh secret: 32 random bytes, hexadecimal (no quoting, no shell meaning)."""
    return secrets.token_bytes(SECRET_BYTES).hex().encode()


def store_login(tools, login: str, secret: bytes) -> str:
    """One of the operator tool's logins, into the System keychain; returns the item's
    name, which is all the installation log records."""
    item = LOGIN_ITEMS[login]
    tools.keychain_add(item, KEYCHAIN_ACCOUNT, secret)
    return item


def store_volume_passphrase(tools, secret: bytes) -> str:
    tools.keychain_add(VOLUME_ITEM, KEYCHAIN_ACCOUNT, secret)
    return VOLUME_ITEM


def present(tools, login: str) -> bool:
    return bool(tools.keychain_has(LOGIN_ITEMS[login]))


def write_secret_file(path: Path, value: dict, *, uid: int, gid: int, base: Path,
                      tools=None) -> None:
    """A holder's secret file: created new at 0600 (never through a link), then given to
    its account. An existing file is never replaced here; a changed password goes through
    the in-person `docsuri-installer change-password`, which rewrites it together with the
    role's new verifier (`password_change.py`; § 6.1)."""
    write_secret_bytes(path, json.dumps(value, sort_keys=True).encode(), uid=uid, gid=gid,
                       base=base, tools=tools)


def write_secret_bytes(path: Path, data: bytes, *, uid: int, gid: int, base: Path,
                       tools=None) -> None:
    """A holder's secret file of raw bytes. Its folder (the holder's own, which the holder
    could change) is reached only through folder descriptors from `base`, the root-owned
    prefix, with no default so no caller can lose the walk (your answer of 2026-11-10,
    "Fix both and sweep the rest"); the file is created relative to that folder's
    descriptor with `O_EXCL | O_NOFOLLOW` at 0600 and given to its account through its
    own descriptor before it is closed: `os.fchown` as root, the tools' `fchown`
    otherwise (the tests' recorded owner)."""

    def give(descriptor: int) -> None:
        if os.geteuid() == 0:
            os.fchown(descriptor, uid, gid)
        elif tools is not None:
            tools.fchown(descriptor, uid, gid)

    safe_fs.create_new(base, path, data, mode=0o600, give=give)
