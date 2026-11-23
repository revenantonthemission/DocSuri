"""U6:NFR3.2/key-never-elsewhere: key material lives only in its own file (design §4).

No encoding of any retained key reaches a stored record, an envelope, a log line, an
error or a traceback frame; the repository and the run folder never hold key material;
and the folder holds exactly its three files after the full lifecycle.
"""

import base64
import json
import logging
import os
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from backend.modules.export import token_keyring
from backend.modules.export.errors import ProtectionUnavailable
from backend.modules.export.token_keyring import (
    KEY_FILE,
    LOCK_FILE,
    MARKER_FILE,
    STAGING_NAME,
    STAGING_PREFIX,
    KeyOperationRefused,
    TokenKeyring,
)
from backend.modules.export.token_vault import TokenVault
from scripts import verify_docsuri_u6 as runner
from tests.u6_approved_export import service_flows as sf

REPOSITORY = Path(__file__).resolve().parents[3]
RUN_ID = "docsuri-u6-key-never-elsewhere"


class Witness:
    """The key counts the ring asks its store for; a mapping of version to count."""

    def __init__(self, counts=None):
        self.counts = counts or {}

    def token_key_counts(self):
        return [
            {"token_key_version": version, "sealed_tokens": count}
            for version, count in self.counts.items()
        ]


def encodings_of(folder: Path) -> list[str]:
    """Every encoding (stored base64, unpadded, urlsafe, hex) of each retained key."""
    record = json.loads((folder / KEY_FILE).read_text())
    values = []
    for encoded in record["keys"].values():
        raw = base64.b64decode(encoded)
        values += [
            encoded,
            encoded.rstrip("="),
            base64.urlsafe_b64encode(raw).decode(),
            raw.hex(),
        ]
    return values


def private_root(tmp_path: Path) -> Path:
    folder = tmp_path / "export-keys"
    folder.mkdir(mode=0o700)
    return folder


def test_no_key_encoding_reaches_any_export_record_or_envelope(
    transactions, connect, authority, tmp_path, operator
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    ring = rig.service.vault._keys
    with ring.holding() as held:
        held.rotate()
    values = encodings_of(ring.root)

    tables = (
        "connection",
        "connection_pace",
        "preview_pair",
        "preview_revision",
        "approval",
        "effect",
        "attempt",
        "reconciliation_check",
        "replay_record",
        "lifecycle_evidence",
        "lifecycle_counts",
        "lane_status",
    )
    stored = [
        operator.execute(
            f"SELECT coalesce(string_agg(to_jsonb(t)::text,' '),'') AS text "
            f"FROM export.{table} t"
        ).fetchone()["text"]
        for table in tables
    ]
    stored.append(
        operator.execute(
            "SELECT coalesce(string_agg(encode(sealed_token,'hex')||':'||"
            "encode(sealed_token,'base64'),' '),'') AS text FROM export.connection"
        ).fetchone()["text"]
    )
    versions = operator.execute(
        "SELECT DISTINCT token_key_version AS version FROM export.connection "
        "WHERE token_key_version IS NOT NULL"
    ).fetchall()

    for value in values:
        assert all(value not in text for text in stored), value
    assert versions and all(
        token_keyring.VERSION.fullmatch(row["version"]) for row in versions
    )


def test_key_material_never_reaches_a_log_line_or_an_error(tmp_path, caplog):
    folder = private_root(tmp_path)
    for name in ("", "backend", "backend.key_custody", "backend.modules.export.token_keyring"):
        caplog.set_level(logging.DEBUG, logger=name)
    witness = Witness()
    ring = TokenKeyring(folder, RUN_ID, witness)
    ring.load()
    vault = TokenVault(ring)
    account, connection = uuid4(), uuid4()

    envelope, version = vault.seal(
        "synthetic-secret-token", account_id=account, connection_id=connection, revision=1
    )
    assert (
        vault.open(envelope, account_id=account, connection_id=connection, revision=1)
        == "synthetic-secret-token"
    )

    operations, retire_refusal, rotate_refusal = [], None, None
    with ring.holding() as held:
        operations.append(held.rotate())
        operations.append(held.rotate())
        active = held.read()["active"]
        oldest = next(version for version in held.read()["keys"] if version != active)
        witness.counts = {oldest: 1}
        try:
            held.retire(oldest)
        except KeyOperationRefused as error:
            retire_refusal = error
        try:
            held.rotate()
        except KeyOperationRefused as error:
            rotate_refusal = error

    (folder / KEY_FILE).chmod(0o644)
    custody_error = None
    try:
        ring.load()
    except ProtectionUnavailable as error:
        custody_error = error
    (folder / KEY_FILE).chmod(0o600)

    values = encodings_of(folder)
    text = caplog.text + "".join(str(vars(record)) for record in caplog.records)
    payloads = [
        json.dumps(item) for item in operations
    ] + [
        repr(retire_refusal),
        str(vars(retire_refusal)),
        json.dumps(retire_refusal.counts or {}),
        repr(rotate_refusal),
        str(vars(rotate_refusal)),
        json.dumps(rotate_refusal.counts or {}),
        repr(custody_error),
        str(vars(custody_error)),
    ]

    assert str(retire_refusal) == "version-in-use"
    assert str(rotate_refusal) == "oldest-version-in-use"
    assert str(custody_error) == custody_error.category
    for value in values:
        assert value not in text, value
        assert all(value not in payload for payload in payloads), value


def test_a_broken_key_file_refuses_without_leaking_its_bytes(tmp_path):
    folder = private_root(tmp_path)
    ring = TokenKeyring(folder, RUN_ID, Witness())
    ring.load()
    values = encodings_of(folder)
    path = folder / KEY_FILE
    original = path.read_text()
    path.write_text(original[:-1])  # the file's own text minus the final brace
    path.chmod(0o600)
    listing_before = sorted(os.listdir(folder))

    with pytest.raises(ProtectionUnavailable) as raised:
        ring.load()

    error = raised.value
    assert str(error) == "key-custody-broken"
    assert error.__cause__ is None and error.__context__ is None
    frame = error.__traceback__
    while frame is not None:
        if frame.tb_frame.f_code.co_filename != __file__:
            for value in frame.tb_frame.f_locals.values():
                text = repr(value)
                for encoding in values:
                    assert encoding not in text
        frame = frame.tb_next
    for encoding in values:
        assert encoding not in repr(error) and encoding not in str(vars(error))
    assert sorted(os.listdir(folder)) == listing_before


def test_the_repository_and_the_run_folder_never_hold_key_material():
    listed = [
        name
        for name in subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=REPOSITORY,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.split("\0")
        if name
    ]

    for name in (KEY_FILE, LOCK_FILE, MARKER_FILE):
        assert all(Path(path).name != name for path in listed)
    assert all(STAGING_NAME.fullmatch(Path(path).name) is None for path in listed)
    assert all("export-keys/" not in path for path in listed)
    run_parent = runner.RUN.parent.resolve()
    assert runner.RUN.is_relative_to(run_parent)
    assert not runner.RUN.is_relative_to(REPOSITORY)
    assert (runner.RUN / runner.KEY_FOLDER).is_relative_to(run_parent)


def test_the_key_folder_holds_only_its_three_files_after_the_full_lifecycle(tmp_path):
    folder = private_root(tmp_path)
    ring = TokenKeyring(folder, RUN_ID, Witness())
    ring.load()

    with ring.holding() as held:
        for _ in range(4):
            held.rotate()
        active = held.read()["active"]
        oldest = next(version for version in held.read()["keys"] if version != active)
        held.retire(oldest)

    (folder / KEY_FILE).unlink()
    with ring.holding() as held:
        held.create_after_loss()

    assert sorted(os.listdir(folder)) == sorted([KEY_FILE, LOCK_FILE, MARKER_FILE])
    assert (folder / KEY_FILE).stat().st_nlink == 1
    assert not [name for name in os.listdir(folder) if name.startswith(STAGING_PREFIX)]
    assert sorted(os.listdir(tmp_path)) == ["export-keys"]
