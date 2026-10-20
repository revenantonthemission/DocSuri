"""U6's token keyring, built on the shared custody helper (security design §4.2–§4.5).

New behaviour over the helper, each with its own tests:

- the key folder itself is checked at every load and before every key command (§4.3);
- versions are `u6-<32 hex>`, and the generation rises by one with every change to the
  key record, from 1 up to 2,147,483,647, so rotation and retirement never run out;
- the first key is published by linking a synced staging file into place, so two
  processes can never both create one; the loser reads the winner's file, and the
  staging name is always removed;
- the key file comes first, then the marker; a missing marker is repaired;
- a waiting lock retries the helper's non-blocking lock, then fails closed;
- leftover staging files are removed under the lock at the next creation or rotation;
- there is no cache: every read goes to the file;
- the first-start decision uses U6's store as a second witness (§4.4, D3), and a failed
  count means protection unavailable (R-16).

The key-folder names and the staging-name pattern are defined here and nowhere else;
the destructive archive (`scripts/u6_preservation.py`) imports them (R-05).

Every custody fault raises `ProtectionUnavailable` with a fixed category, raised after
any `except` block has ended, so it never carries a cause or context that could hold
key material (the JSON decoder keeps the whole document on its error).
"""

from __future__ import annotations

import base64
import os
import re
import secrets
import stat
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from backend import key_custody
from backend.modules.export.errors import ProtectionUnavailable
from backend.u6_policy import SYNTHETIC_EXPORT, ExportPolicy

KEY_FILE = "export-token-keyring.json"
LOCK_FILE = "export-token-keyring.lock"
MARKER_FILE = "export-token-keyring.initialized"
STAGING_PREFIX = ".export-key-"
STAGING_NAME = re.compile(re.escape(STAGING_PREFIX) + r"[0-9a-f]{32}")
VERSION_PATTERN = r"u6-[0-9a-f]{32}"
VERSION = re.compile(VERSION_PATTERN)
GENERATION_MAX = 2_147_483_647
MAX_VERSIONS = 3

SETTINGS = key_custody.CustodySettings(
    filename=KEY_FILE,
    lock_name=LOCK_FILE,
    marker_name=MARKER_FILE,
    staging_prefix=STAGING_PREFIX,
    version_pattern=VERSION_PATTERN,
    generation_min=1,
    generation_max=GENERATION_MAX,
    error=ProtectionUnavailable,
    lock_message="key-lock-unavailable",
    custody_message="key-custody-broken",
    missing_key_message="key-version-unavailable",
    max_versions=MAX_VERSIONS,
)

# The §4.4 decision table's outcomes.
NORMAL = "normal"
REPAIR = "repair"
FIRST_START = "first-start"
LOSS = "loss"


class KeyStore(Protocol):
    """The second witness: sealed tokens per key version, with no identifiers."""

    def token_key_counts(self) -> list: ...


class KeyOperationRefused(RuntimeError):
    """A key operation that would break custody rules; carries counts only."""

    def __init__(self, category: str, counts: Mapping[str, int] | None = None):
        super().__init__(category)
        self.category = category
        self.counts = dict(counts or {})


def service_uid() -> int:
    """The user the key folder must belong to; one seam for the foreign-owner test."""
    return os.getuid()


def check_key_folder(root: Path) -> None:
    """§4.3: a directory, not a link, owned by the service user, closed to everyone else.

    Anything else raises `ProtectionUnavailable` and creates nothing.
    """
    unavailable = False
    try:
        info = root.lstat()
    except OSError:
        unavailable = True
    else:
        unavailable = (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != service_uid()
            or stat.S_IMODE(info.st_mode) & 0o077 != 0
        )
    if unavailable:
        raise ProtectionUnavailable("key-folder-unavailable")


def decide(key_present: bool, marker_present: bool, sealed_tokens: int | None) -> str:
    """The §4.4 table for an absent or valid key file (a broken one raises earlier).

    `sealed_tokens` is only needed, and only consulted, when both files are absent.
    """
    if key_present:
        return NORMAL if marker_present else REPAIR
    if marker_present:
        return LOSS
    if sealed_tokens is None:
        raise ProtectionUnavailable("key-count-unavailable")
    return FIRST_START if sealed_tokens == 0 else LOSS


def _normalise_counts(rows) -> dict[str, int]:
    if not isinstance(rows, list | tuple):
        raise ValueError("key counts must be rows")
    counts: dict[str, int] = {}
    for row in rows:
        if isinstance(row, Mapping):
            version, count = row["token_key_version"], row["sealed_tokens"]
        else:
            version, count = row
        if (
            not isinstance(version, str)
            or VERSION.fullmatch(version) is None
            or type(count) is not int
            or count < 1
            or version in counts
        ):
            raise ValueError("malformed key count row")
        counts[version] = count
    return counts


def _fresh_record(run_id: str, generation: int) -> tuple[str, dict]:
    version = "u6-" + uuid4().hex
    record = {
        "runId": run_id,
        "active": version,
        "generation": generation,
        "keys": {version: base64.b64encode(secrets.token_bytes(32)).decode()},
    }
    return version, record


class TokenKeyring:
    """The token keyring over one key folder; it reads the key file on every call."""

    def __init__(
        self,
        root: Path,
        run_id: str,
        store: KeyStore,
        *,
        policy: ExportPolicy = SYNTHETIC_EXPORT,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not isinstance(root, Path) or not isinstance(run_id, str) or not run_id:
            raise ValueError("key folder and run id required")
        self.root, self.run_id, self.store = root, run_id, store
        self._retry_seconds = policy.key_lock_retry_ms / 1000
        self._wait_seconds = policy.key_lock_wait_ms / 1000
        self._clock, self._sleep = clock, sleep

    # Checks -------------------------------------------------------------------------

    def check_folder(self) -> None:
        check_key_folder(self.root)

    def counts(self) -> dict[str, int]:
        """The witness's counts; any failure or malformed answer is unavailable (R-16)."""
        counts = None
        try:
            counts = _normalise_counts(self.store.token_key_counts())
        except Exception:  # every witness fault fails closed (R-16); the cause is dropped
            pass
        if counts is None:
            raise ProtectionUnavailable("key-count-unavailable")
        return counts

    def _present(self, name: str) -> bool:
        path = self.root / name
        return path.exists() or path.is_symlink()

    def _read_file(self) -> dict:
        record = None
        try:
            record = key_custody.read_record(SETTINGS, self.root, self.run_id)
        except ProtectionUnavailable:
            pass
        if record is None:
            raise ProtectionUnavailable("key-custody-broken")
        return record

    # Reads --------------------------------------------------------------------------

    def load(self) -> dict:
        """Apply the §4.4 table: use, repair, create the first key, or refuse."""
        self.check_folder()
        key_present, marker_present = self._present(KEY_FILE), self._present(MARKER_FILE)
        if key_present:
            record = self._read_file()
            if not marker_present:
                with self.holding() as held:
                    held.ensure_marker()
            return record
        if marker_present:
            raise ProtectionUnavailable("key-lost")
        if decide(False, False, sum(self.counts().values())) == LOSS:
            raise ProtectionUnavailable("key-lost")
        with self.holding() as held:
            return held.obtain_first()

    def key(self, version: str) -> bytes:
        return self._retained(self.load(), version)

    def active_key(self) -> tuple[str, bytes]:
        record = self.load()
        return record["active"], self._retained(record, record["active"])

    @staticmethod
    def _retained(record: dict, version: str) -> bytes:
        key = None
        try:
            key = key_custody.retained_key(SETTINGS, record, version)
        except (ProtectionUnavailable, ValueError):
            pass
        if key is None:
            raise ProtectionUnavailable("key-version-unavailable")
        return key

    # Lock ---------------------------------------------------------------------------

    @contextmanager
    def holding(self) -> Iterator[HeldKeyring]:
        """Check the folder, take the waiting lock, and yield the locked view."""
        self.check_folder()
        with ExitStack() as stack:
            self._acquire(stack)
            yield HeldKeyring(self)

    def _acquire(self, stack: ExitStack) -> None:
        deadline = self._clock() + self._wait_seconds
        while True:
            failure = None
            try:
                stack.enter_context(key_custody.exclusive_lock(SETTINGS, self.root))
                return
            except BlockingIOError:
                failure = "busy"
            except (OSError, ProtectionUnavailable):
                failure = "custody"
            if failure == "custody" or self._clock() >= deadline:
                break
            self._sleep(self._retry_seconds)
        raise ProtectionUnavailable("key-lock-unavailable")


class HeldKeyring:
    """Key-record operations that run only while the keyring's waiting lock is held."""

    def __init__(self, keyring: TokenKeyring):
        self._ring = keyring

    @property
    def root(self) -> Path:
        return self._ring.root

    def assess(self) -> str:
        """The §4.4 outcome; a key file that fails any check raises."""
        ring = self._ring
        key_present, marker_present = ring._present(KEY_FILE), ring._present(MARKER_FILE)
        if key_present:
            ring._read_file()
            return decide(True, marker_present, None)
        if marker_present:
            return LOSS
        return decide(False, False, sum(ring.counts().values()))

    def read(self) -> dict:
        """The current record, repairing a missing marker; an absent key refuses."""
        if not self._ring._present(KEY_FILE):
            raise ProtectionUnavailable("key-lost")
        record = self._ring._read_file()
        self.ensure_marker()
        return record

    def key(self, version: str) -> bytes:
        return TokenKeyring._retained(self.read(), version)

    def active_key(self) -> tuple[str, bytes]:
        record = self.read()
        return record["active"], TokenKeyring._retained(record, record["active"])

    def ensure_marker(self) -> None:
        """Write the marker only if it is absent (repair after an interrupted creation)."""
        if not self._ring._present(MARKER_FILE):
            self._guarded(lambda: key_custody.create_marker(SETTINGS, self.root, self._ring.run_id))

    def clean_staging(self) -> int:
        """Remove staging files a crash left behind; returns how many were removed."""
        removed = 0
        for entry in os.scandir(self.root):
            if STAGING_NAME.fullmatch(entry.name):
                self._guarded(lambda name=entry.name: (self.root / name).unlink(missing_ok=True))
                removed += 1
        if removed:
            self._guarded(lambda: key_custody.sync_folder(self.root))
        return removed

    def obtain_first(self) -> dict:
        """First start, re-checked under the lock: create the key, or read the winner's."""
        outcome = self.assess()
        if outcome == LOSS:
            raise ProtectionUnavailable("key-lost")
        if outcome == FIRST_START:
            self._link_new_key(generation=1)
        return self.read()

    def create_after_loss(self) -> dict:
        """`create-key-after-loss`: only when the table says loss (§4.5)."""
        outcome = self.assess()
        if outcome != LOSS:
            raise KeyOperationRefused("not-a-loss")
        if self._ring._present(KEY_FILE):
            raise KeyOperationRefused("not-a-loss")
        self._link_new_key(generation=1)
        return self.read()

    def _link_new_key(self, *, generation: int) -> None:
        """Publish a fresh key by linking a synced staging file into place."""
        self.clean_staging()
        _, record = _fresh_record(self._ring.run_id, generation)
        staging = self._guarded(lambda: key_custody.stage(SETTINGS, self.root, record))
        linked = False
        try:
            try:
                os.link(staging, self.root / KEY_FILE)
                linked = True
            except FileExistsError:
                linked = True  # another process won; its file is read below
            except OSError:
                pass
        finally:
            self._guarded(lambda: staging.unlink(missing_ok=True))
        if not linked:
            self._fail()
        self._guarded(lambda: key_custody.sync_folder(self.root))
        self.ensure_marker()

    def rotate(self) -> dict:
        """Add a new active version; with three present, first retire the oldest.

        The oldest is retired only while no token is sealed under it; otherwise the
        rotation refuses and reports the counts, so the file never holds a fourth version.
        """
        record = self.read()
        self.clean_staging()
        retired = None
        if len(record["keys"]) >= MAX_VERSIONS:
            counts = self._ring.counts()
            oldest = next(v for v in record["keys"] if v != record["active"])
            if counts.get(oldest, 0) != 0:
                raise KeyOperationRefused("oldest-version-in-use", counts)
            del record["keys"][oldest]
            retired = oldest
            self._advance(record)
        version, fresh = _fresh_record(self._ring.run_id, 1)
        record["keys"][version] = fresh["keys"][version]
        record["active"] = version
        self._advance(record)
        self._publish(record)
        return {"activeVersion": version, "generation": record["generation"], "retired": retired}

    def retire(self, version: str) -> dict:
        """Remove a version that is not active and seals no token, both checked now."""
        record = self.read()
        if version == record["active"]:
            raise KeyOperationRefused("active-version")
        if version not in record["keys"]:
            raise KeyOperationRefused("version-absent")
        counts = self._ring.counts()
        if counts.get(version, 0) != 0:
            raise KeyOperationRefused("version-in-use", counts)
        del record["keys"][version]
        self._advance(record)
        self._publish(record)
        return {"activeVersion": record["active"], "generation": record["generation"]}

    @staticmethod
    def _advance(record: dict) -> None:
        if record["generation"] >= GENERATION_MAX:
            raise KeyOperationRefused("generation-exhausted")
        record["generation"] += 1

    def _publish(self, record: dict) -> None:
        self._guarded(lambda: key_custody.write(SETTINGS, self.root, record))

    def _guarded(self, action):
        """Run a file step; any operating-system fault becomes protection unavailable."""
        failed, result = False, None
        try:
            result = action()
        except OSError:
            failed = True
        if failed:
            self._fail()
        return result

    @staticmethod
    def _fail():
        raise ProtectionUnavailable("key-write-unavailable")
