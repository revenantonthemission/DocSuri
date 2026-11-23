"""AccountAccess's verifier key and production's control keyring (U8 plan Steps 11, 19, 21
and 37; BR6.2; C02 4.0.0 `access.replaceVerifierKey`).

- **The verifier key.** v2's first start creates it once its database answers
  (`ensure_verifier_key`). Its replacement (`replace_verifier_key`) ends every session
  and outstanding proof; the production environment tool runs it in person while v2's
  processes are stopped (a running process keeps the key it read at its start). The key
  read applies the same custody checks as `GuardedEntryService`'s constructor: a regular
  file owned by this process's user, mode 0600, one link, and never a symlink.
- **The control keyring's start and U8's keyring snapshot** (your decisions of
  2026-10-24, "Add a key snapshot step", and of 2026-10-25, "Start it at install, U8
  snapshot"). `start_keyring` starts the keyring in the profile's `control-keys/` once,
  with U2's own `ControlKeyring.rotate`: a new active key and the start marker, with the
  key derived from the verifier key kept for reading only. From then on new sign-in
  secrets use the started key, so a verifier replacement neither blocks on them nor
  loses them. It then writes U8's keyring snapshot: the keyring's record and its start
  marker's run, with no verifier, written once and never replaced. Because it holds no
  verifier, the snapshot stays valid after a replacement.
- **Production key recovery** (`recover_production`, the production tool's
  `control-key-recovery`). It restores only the keyring's missing files, its record and
  its start marker, from U8's snapshot named by its exact digest and generation. It
  refuses another folder, a missing snapshot or a divergent current file before it
  writes anything, and never writes the verifier.

U2's own `control_key_recovery.py` stays as built, with U2's test folder and U2's
snapshot format.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import os
import re
import secrets
import stat
from pathlib import Path

VERIFIER_KEY_ABSENT = "absent"
REPLACEMENT_REASONS = ("verifier-key-lost", "verifier-key-exposed", "verifier-key-rotation")
_KEY_BYTES = 32
# How long a start waits for a key another start is linking into place to settle at
# one link (its staging name unlinked), before it reads the key.
SETTLE_SECONDS = 5.0


def _settled(path: Path, *, seconds: float = SETTLE_SECONDS) -> None:
    """Wait until the key at `path` has exactly one link: a concurrent start that linked
    it from its staging file unlinks the staging name at once, and only then may anyone
    read it (its custody checks refuse a second link)."""
    import time

    deadline = time.monotonic() + seconds
    while True:
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise ValueError("start key custody invalid")
        if info.st_nlink == 1:
            return
        if time.monotonic() >= deadline:
            raise ValueError("start key never settled at one link")
        time.sleep(0.01)


def ensure_key_file(path: Path, *, size: int = _KEY_BYTES) -> bool:
    """A start's key (U8 plan Step 11; BR6.2), created only when missing: written whole
    to a staging file of its own beside it (0600), linked into place, and the staging
    name unlinked. Concurrent starts therefore keep one key (the second link finds the
    first in place) and no process reads a partial one. Returns whether this call made
    the key."""
    try:
        path.lstat()
    except FileNotFoundError:
        pass
    else:
        _settled(path)
        return False
    staging = path.parent / (f".{path.name}-" + secrets.token_hex(8))
    descriptor = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    created = False
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(secrets.token_bytes(size))
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(staging, path)
            created = True
        except FileExistsError:
            created = False
    finally:
        staging.unlink(missing_ok=True)
    folder = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(folder)
    finally:
        os.close(folder)
    _settled(path)
    return created


def ensure_verifier_key(profile) -> bool:
    """AccountAccess's verifier key, created when missing, before any builder runs (the
    composition calls it once the database answers and no account exists, or the key is
    already present). `GuardedEntryService` then only reads it."""
    from backend.local_profile import verifier_key_path

    return ensure_key_file(verifier_key_path(profile))


def _read_key(path: Path) -> bytes | None:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    except OSError as error:
        # O_NOFOLLOW on a symlink: the key is never read through a link.
        raise ValueError("account verifier key custody invalid") from error
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
        ):
            raise ValueError("account verifier key custody invalid")
        key = stream.read(_KEY_BYTES + 1)
    if len(key) != _KEY_BYTES:
        raise ValueError("account verifier key incomplete")
    return key


def verifier_key_revision(path: Path) -> str:
    """The key's public revision: a keyed digest under its own purpose, never the key;
    `absent` when the key is lost."""
    key = _read_key(path)
    if key is None:
        return VERIFIER_KEY_ABSENT
    return hmac.new(key, b"docsuri-verifier-key-revision", hashlib.sha256).hexdigest()[:32]


def _end_everything(conn) -> tuple[int, int]:
    """End every session and every outstanding proof; nothing signed under the old key
    verifies again. Returns the two counts."""
    sessions = conn.execute(
        "UPDATE accounts.session SET revoked=true WHERE NOT revoked"
    ).rowcount
    proofs = conn.execute(
        "UPDATE accounts.control_proof SET expires_at=clock_timestamp() "
        "WHERE consumed_at IS NULL AND expires_at>clock_timestamp()"
    ).rowcount
    proofs += conn.execute(
        "UPDATE accounts.challenge SET consumed=true WHERE NOT consumed"
    ).rowcount
    proofs += conn.execute(
        "UPDATE accounts.identity_flow SET disposition='expired' "
        "WHERE disposition IN ('pending','exchanging')"
    ).rowcount
    proofs += conn.execute(
        "UPDATE accounts.mfa_enrollment SET state='invalidated' WHERE state='inactive'"
    ).rowcount
    # A reset confirmation is consumed only through its own session, which has ended.
    proofs += conn.execute(
        "SELECT count(*) AS n FROM accounts.reset_confirmation WHERE consumed_operation "
        "IS NULL AND expires_at>clock_timestamp()"
    ).fetchone()["n"]
    return sessions, proofs


def replace_verifier_key(
    transactions, *, expected_key_revision: str, reason_key: str, now: dt.datetime,
    key_path: Path | None = None,
) -> dict:
    """Replace the verifier key.

    A stale `expected_key_revision` changes nothing. While the key is present, an active
    second factor still protected under the key-derived legacy version would become
    unreadable, so the replacement refuses until the control keyring re-protects it;
    once the key is lost that material is already unreadable. Every session and
    outstanding proof ends in one transaction, then the new key replaces the old one."""
    from backend.local_profile import verifier_key_path
    from backend.modules.accounts.control_policy import PolicyUnavailable

    if reason_key not in REPLACEMENT_REASONS:
        raise ValueError("replacement reason outside the registered set")
    if now.tzinfo is None:
        raise ValueError("the replacement time must be aware")
    path = key_path or verifier_key_path(transactions.profile)
    if verifier_key_revision(path) != expected_key_revision:
        raise ValueError("stale verifier key revision")
    present = expected_key_revision != VERIFIER_KEY_ABSENT
    staging = path.parent / (".verifier-key-" + secrets.token_hex(8))
    descriptor = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(secrets.token_bytes(_KEY_BYTES))
            stream.flush()
            os.fsync(stream.fileno())

        def write(conn):
            conn.execute("LOCK TABLE accounts.session IN SHARE ROW EXCLUSIVE MODE")
            if present and conn.execute(
                "SELECT 1 FROM accounts.mfa_enrollment WHERE state='active' "
                "AND key_version='u2-v1' LIMIT 1"
            ).fetchone():
                raise PolicyUnavailable("legacy-protected factors need re-protection first")
            return _end_everything(conn)

        sessions, proofs = transactions.run("accounts", write)
        os.replace(staging, path)
    except BaseException:
        staging.unlink(missing_ok=True)
        raise
    folder = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(folder)
    finally:
        os.close(folder)
    return {
        "keyRevision": verifier_key_revision(path),
        "sessionsEnded": sessions,
        "proofsEnded": proofs,
        "replacedAt": now.isoformat(),
    }


# --- production's control keyring: its start, U8's snapshot and its recovery ---------------

CONTROL_KEYS = "control-keys"
VERIFIER_FOLDER = "verifier-key"
SNAPSHOT_FOLDER = "u8-keyring-snapshot"
SNAPSHOT_KIND = "docsuri-u8-control-keyring"
SNAPSHOT_FIELDS = frozenset({"version", "kind", "runId", "generation", "keyring", "marker"})
_SNAPSHOT_NAME = re.compile(r"[0-9a-f]{64}\.json")
_SNAPSHOT_BYTES = 8192
_RING_BYTES = 4096
_MARKER_BYTES = 128


class KeyringRefused(Exception):
    """A keyring start or recovery refused before it wrote anything; `reason` is a fixed
    key, never a value."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _folder_custody(folder: Path) -> None:
    """A key folder: a real folder, never a link, this process's user's, mode 0700."""
    try:
        info = folder.lstat()
    except FileNotFoundError:
        raise KeyringRefused("folder-missing") from None
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise KeyringRefused("folder-custody")


def _private_read(path: Path, maximum: int) -> bytes:
    """A custody file: regular, never through a link, this user's, 0600, one link and
    within its bound."""
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise KeyringRefused("file-custody") from None
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
            or info.st_size > maximum
        ):
            raise KeyringRefused("file-custody")
        return stream.read(maximum + 1)


def _write_new(path: Path, content: bytes) -> None:
    """A file that does not exist yet, created exclusively (0600, never through a link),
    synced, then its folder synced."""
    from backend import key_custody

    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    key_custody.sync_folder(path.parent)


def _legacy_key(verifier_path: Path) -> bytes:
    """The key derived from the verifier key: what `GuardedEntryService.verifier`
    derives for `("encryption", "u2-controls-v1")`, the keyring's `u2-v1` version."""
    try:
        key = _read_key(verifier_path)
    except ValueError:
        raise KeyringRefused("verifier-key-custody") from None
    if key is None:
        raise KeyringRefused("verifier-key-missing")
    return hmac.new(key, b"encryption\0u2-controls-v1", hashlib.sha256).digest()


def _snapshot_file(keys: Path) -> Path | None:
    """U8's one keyring snapshot in `control-keys/`, or None when none was written."""
    folder = keys / SNAPSHOT_FOLDER
    if not folder.exists() and not folder.is_symlink():
        return None
    _folder_custody(folder)
    entries = list(folder.iterdir())
    if any(not _SNAPSHOT_NAME.fullmatch(entry.name) for entry in entries) or len(entries) > 1:
        raise KeyringRefused("snapshot-folder-differs")
    return entries[0] if entries else None


def snapshot_present(profile_root: Path) -> bool:
    """Whether U8's keyring snapshot is in place: a read-only look the installer makes as
    root (so it checks no owner), before it runs `control-key-start`."""
    folder = profile_root / CONTROL_KEYS / SNAPSHOT_FOLDER
    return folder.is_dir() and any(
        _SNAPSHOT_NAME.fullmatch(entry.name) for entry in folder.iterdir()
    )


def _snapshot_identity(path: Path, run_id: str) -> dict:
    data = _private_read(path, _SNAPSHOT_BYTES)
    value = _snapshot_value(data, run_id)
    return {"generation": value["generation"], "digest": hashlib.sha256(data).hexdigest()}


def _snapshot_value(data: bytes, run_id: str) -> dict:
    """A snapshot's content, checked: its fields, version, kind and run, its record as
    the keyring's own guarded read would accept it, and the record's generation."""
    from backend import key_custody
    from backend.modules.accounts.control_keys import ControlKeyring

    try:
        value = json.loads(data)
        if (
            not isinstance(value, dict)
            or set(value) != SNAPSHOT_FIELDS
            or value["version"] != 1
            or value["kind"] != SNAPSHOT_KIND
            or value["runId"] != run_id
            or value["marker"] != run_id
            or type(value["generation"]) is not int
        ):
            raise ValueError("snapshot form")
        key_custody._check_record(ControlKeyring.custody, value["keyring"], run_id)
        if value["keyring"]["generation"] != value["generation"]:
            raise ValueError("snapshot generation")
    except (ValueError, TypeError, KeyError):
        raise KeyringRefused("snapshot-differs") from None
    return value


def start_keyring(profile_root: Path, run_id: str) -> dict:
    """Start production's control keyring once and write U8's keyring snapshot (the
    production tool's `control-key-start`, run in person while v2 is stopped).

    It reads the verifier key and writes nothing outside `control-keys/`. With the
    keyring not yet started it rotates it with U2's own `ControlKeyring.rotate`; with it
    started it leaves it alone. It then takes only a snapshot that is missing, so a start
    cut short between the rotation and the snapshot is completed by running it again,
    and with both in place it changes nothing. Any refusal comes before the first write.
    """
    from backend.modules.accounts.control_keys import ControlKeyring
    from backend.modules.accounts.control_policy import PolicyUnavailable

    keys = profile_root / CONTROL_KEYS
    for folder in (keys, profile_root / VERIFIER_FOLDER):
        _folder_custody(folder)
    legacy = _legacy_key(profile_root / VERIFIER_FOLDER / "account-verifier.key")
    existing = _snapshot_file(keys)
    try:
        ring = ControlKeyring(keys, run_id, legacy, production_root=profile_root)
    except (PolicyUnavailable, ValueError):
        raise KeyringRefused("keyring-custody") from None
    started = False
    absent = not (keys / ControlKeyring.filename).exists()
    if absent and existing is not None:
        # A snapshot means the keyring was started: a missing record is recovered from
        # it (`control-key-recovery`), never started again under a new key.
        raise KeyringRefused("keyring-missing-use-recovery")
    if absent:
        try:
            ring.rotate()
        except BlockingIOError:
            raise KeyringRefused("keyring-busy") from None
        started = True
    if existing is not None:
        return {"runId": run_id, **_snapshot_identity(existing, run_id),
                "activeVersion": ring.active_version, "started": started,
                "snapshotWritten": False}
    return {"runId": run_id, **_write_snapshot(ring, keys, run_id), "started": started,
            "snapshotWritten": True}


def _write_snapshot(ring, keys: Path, run_id: str) -> dict:
    """U8's keyring snapshot, under the keyring's own lock: its record and its start
    marker's run, no verifier, named by the SHA-256 of its bytes."""
    from backend.modules.accounts.control_policy import PolicyUnavailable

    try:
        with ring._lock():
            record = ring.read()
            marker = _private_read(keys / ring.custody.marker_name, _MARKER_BYTES)
            if marker != run_id.encode():
                raise KeyringRefused("marker-run-differs")
            data = json.dumps(
                {"version": 1, "kind": SNAPSHOT_KIND, "runId": run_id,
                 "generation": record["generation"], "keyring": record, "marker": run_id},
                sort_keys=True, separators=(",", ":"),
            ).encode()
            _snapshot_value(data, run_id)
            digest = hashlib.sha256(data).hexdigest()
            folder = keys / SNAPSHOT_FOLDER
            if not folder.exists():
                os.mkdir(folder, 0o700)
                os.chmod(folder, 0o700)
            _folder_custody(folder)
            _write_new(folder / f"{digest}.json", data)
    except BlockingIOError:
        raise KeyringRefused("keyring-busy") from None
    except PolicyUnavailable:
        raise KeyringRefused("keyring-custody") from None
    return {"generation": record["generation"], "digest": digest,
            "activeVersion": record["active"]}


def recover_production(
    root: Path, *, profile_root: Path, run_id: str, expected_digest: str,
    expected_generation: int,
) -> dict:
    """Production key recovery from U8's keyring snapshot (the production tool's
    `control-key-recovery`).

    `root` must be exactly the profile's `control-keys/`. The snapshot is the one named by
    `expected_digest`, whose generation must be `expected_generation`. Every present file
    of the keyring, its record and its start marker, must already match the snapshot;
    only a missing one is written, and the verifier key is never read or written. Any
    refusal comes before the first write."""
    from backend import key_custody
    from backend.modules.accounts.control_keys import ControlKeyring

    if (
        not profile_root.is_absolute()
        or root.is_symlink()
        or root.resolve() != profile_root.resolve() / CONTROL_KEYS
    ):
        raise KeyringRefused("recovery-folder-refused")
    if (
        not isinstance(expected_digest, str)
        or not re.fullmatch("[0-9a-f]{64}", expected_digest)
        or type(expected_generation) is not int
        or not 1 <= expected_generation <= 3
    ):
        raise KeyringRefused("recovery-identity-refused")
    _folder_custody(root)
    path = root / SNAPSHOT_FOLDER / f"{expected_digest}.json"
    if not path.exists() and not path.is_symlink():
        raise KeyringRefused("snapshot-missing")
    _folder_custody(path.parent)
    data = _private_read(path, _SNAPSHOT_BYTES)
    if not hmac.compare_digest(hashlib.sha256(data).hexdigest(), expected_digest):
        raise KeyringRefused("snapshot-digest-differs")
    value = _snapshot_value(data, run_id)
    if value["generation"] != expected_generation:
        raise KeyringRefused("snapshot-generation-differs")
    record = value["keyring"]
    custody = ControlKeyring.custody
    # The marker first, as `rotate` writes it: a ring file without it fails closed.
    outputs = (
        (root / custody.marker_name, run_id.encode()),
        (root / custody.filename, json.dumps(record).encode()),
    )
    try:
        with key_custody.exclusive_lock(custody, root):
            for target, content in outputs:
                if target.exists() or target.is_symlink():
                    actual = _private_read(
                        target, _MARKER_BYTES if target.name == custody.marker_name
                        else _RING_BYTES)
                    try:
                        matches = (json.loads(actual) == record
                                   if target.name == custody.filename else actual == content)
                    except ValueError:
                        matches = False
                    if not matches:
                        raise KeyringRefused("divergent-current-file")
            restored = []
            for target, content in outputs:
                if not target.exists():
                    _write_new(target, content)
                    restored.append(target.name)
            key_custody.read_record(custody, root, run_id)
    except BlockingIOError:
        raise KeyringRefused("keyring-busy") from None
    return {"runId": run_id, "generation": expected_generation, "digest": expected_digest,
            "restored": restored}
