"""Operator key commands (security design §4.5; cicd-pipeline §4.5; NFR3.3).

The commands act through the environment tool's administrative connection after
`SET ROLE docsuri_export_owner`, and call only `export.token_key_counts()`,
`export.token_envelopes_for_reseal(version, limit)` and `export.reseal_token(...)`.
Each checks the key folder first and runs under the token keyring's waiting lock.

Every report holds counts and key versions only: never an envelope, a token or a
connection identifier. Refusals raise `KeyOperationRefused` (with counts) or
`ProtectionUnavailable` (a custody fault); the tool's phases print the report.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from psycopg.rows import dict_row, tuple_row

from backend.modules.export.errors import ProtectionUnavailable
from backend.modules.export.token_keyring import (
    VERSION,
    HeldKeyring,
    KeyOperationRefused,
    TokenKeyring,
    check_key_folder,
)
from backend.modules.export.token_vault import TokenVault
from backend.u6_policy import SYNTHETIC_EXPORT, ExportPolicy

OPERATOR_ROLE = "docsuri_export_owner"
RESEAL_PAGE = 100


class OperatorStore:
    """The operator path: an administrative connection acting as the schema owner.

    Each call commits on its own, so the re-seal runs one row at a time.
    """

    def __init__(self, conn):
        self._conn = conn
        with conn.cursor(row_factory=tuple_row) as cursor:
            cursor.execute(f"SET ROLE {OPERATOR_ROLE}")
            role = cursor.execute("SELECT current_user").fetchone()[0]
        conn.commit()
        if role != OPERATOR_ROLE:
            raise KeyOperationRefused("operator-role-required")

    def _rows(self, query: str, params: tuple = ()) -> list[dict]:
        with self._conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(query, params).fetchall()
        self._conn.commit()
        return rows

    def token_key_counts(self) -> list[dict]:
        return self._rows("SELECT token_key_version,sealed_tokens FROM export.token_key_counts()")

    def envelopes_for_reseal(self, version: str, limit: int) -> list[dict]:
        return self._rows(
            "SELECT connection_id,account_id,revision,sealed_token "
            "FROM export.token_envelopes_for_reseal(%s,%s)",
            (version, limit),
        )

    def reseal(self, connection_id, expected_sha256: str, envelope: bytes, version: str) -> bool:
        rows = self._rows(
            "SELECT export.reseal_token(%s,%s,%s,%s) AS resealed",
            (connection_id, expected_sha256, envelope, version),
        )
        return rows[0]["resealed"] is True


def _keyring(key_folder: Path, run_id: str, conn, policy: ExportPolicy) -> TokenKeyring:
    check_key_folder(key_folder)  # before anything touches the database
    return TokenKeyring(key_folder, run_id, OperatorStore(conn), policy=policy)


def key_counts(key_folder: Path, run_id: str, conn, *, policy=SYNTHETIC_EXPORT) -> dict:
    """`key-counts`: sealed tokens per key version."""
    ring = _keyring(key_folder, run_id, conn, policy)
    with ring.holding():
        return {"command": "key-counts", "counts": ring.counts()}


def create_key_after_loss(
    key_folder: Path, run_id: str, conn, *, policy=SYNTHETIC_EXPORT
) -> dict:
    """`create-key-after-loss`: refuses unless §4.4 says loss; reports stranded tokens."""
    ring = _keyring(key_folder, run_id, conn, policy)
    with ring.holding() as held:
        record = held.create_after_loss()
        counts = ring.counts()
    return {
        "command": "create-key-after-loss",
        "activeVersion": record["active"],
        "generation": record["generation"],
        "tokensUnderMissingVersions": _missing(counts, record),
        "counts": counts,
    }


def rotate_key(key_folder: Path, run_id: str, conn, *, policy=SYNTHETIC_EXPORT) -> dict:
    """`rotate-key`: add a new active version, then re-seal row by row (compare-and-set).

    Tokens under a version the key file no longer holds are skipped and reported.
    """
    ring = _keyring(key_folder, run_id, conn, policy)
    with ring.holding() as held:
        rotation = held.rotate()
        record = held.read()
        tally = {"resealed": 0, "conflicts": 0, "unopenable": 0}
        for version in record["keys"]:
            if version != record["active"]:
                _reseal_version(held, ring.store, version, tally)
        counts = ring.counts()
    return {
        "command": "rotate-key",
        "activeVersion": rotation["activeVersion"],
        "generation": rotation["generation"],
        "retiredVersion": rotation["retired"],
        **tally,
        "tokensUnderMissingVersions": _missing(counts, record),
        "counts": counts,
    }


def retire_key(
    key_folder: Path, run_id: str, conn, version: str, *, policy=SYNTHETIC_EXPORT
) -> dict:
    """`retire-key --version <v>`: never the active version, never a version in use."""
    if not isinstance(version, str) or VERSION.fullmatch(version) is None:
        raise KeyOperationRefused("version-invalid")
    ring = _keyring(key_folder, run_id, conn, policy)
    with ring.holding() as held:
        retired = held.retire(version)
        counts = ring.counts()
    return {
        "command": "retire-key",
        "retiredVersion": version,
        "activeVersion": retired["activeVersion"],
        "generation": retired["generation"],
        "counts": counts,
    }


def _missing(counts: dict[str, int], record: dict) -> int:
    return sum(n for version, n in counts.items() if version not in record["keys"])


def _reseal_version(held: HeldKeyring, store: OperatorStore, version: str, tally: dict) -> None:
    """Re-seal every token under `version` with the active key, one row at a time.

    A row whose compare-and-set fails (a concurrent replace) or that cannot be opened is
    attempted once and counted; a later `rotate-key` picks up anything left.
    """
    vault = TokenVault(held)
    attempted: set = set()
    while True:
        rows = [
            row
            for row in store.envelopes_for_reseal(version, RESEAL_PAGE)
            if row["connection_id"] not in attempted
        ]
        if not rows:
            return
        for row in rows:
            attempted.add(row["connection_id"])
            tally[_reseal_row(vault, store, row)] += 1


def _reseal_row(vault: TokenVault, store: OperatorStore, row: dict) -> str:
    old = bytes(row["sealed_token"])
    binding = {
        "account_id": row["account_id"],
        "connection_id": row["connection_id"],
        "revision": row["revision"],
    }
    try:
        token = vault.open(old, **binding)
    except ProtectionUnavailable:
        return "unopenable"
    envelope, new_version = vault.seal(token, **binding)
    del token
    expected = hashlib.sha256(old).hexdigest()
    if store.reseal(row["connection_id"], expected, envelope, new_version):
        return "resealed"
    return "conflicts"
