"""U6's token keyring: folder custody, the §4.4 decisions, first key, lock and rotation."""

import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

import pytest
from backend import key_custody
from backend.modules.accounts.control_keys import ControlKeyring
from backend.modules.export import token_keyring
from backend.modules.export.errors import ProtectionUnavailable
from backend.modules.export.repository import ExportRepository
from backend.modules.export.token_keyring import (
    FIRST_START,
    KEY_FILE,
    LOCK_FILE,
    LOSS,
    MARKER_FILE,
    NORMAL,
    REPAIR,
    SETTINGS,
    STAGING_PREFIX,
    HeldKeyring,
    KeyOperationRefused,
    TokenKeyring,
    decide,
)
from backend.u6_policy import ExportPolicy

from tests.u6_approved_export import export_rows as rows

REPOSITORY = Path(__file__).resolve().parents[3]
RUN = "u6-keyring-test"


class Witness:
    """A store stub for the decision rows that need no database."""

    def __init__(self, counts=None, *, failure=None, raw=None):
        self.counts, self.failure, self.raw, self.calls = counts or {}, failure, raw, 0

    def token_key_counts(self):
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        if self.raw is not None:
            return self.raw
        return [{"token_key_version": v, "sealed_tokens": n} for v, n in self.counts.items()]


def version() -> str:
    return "u6-" + secrets.token_hex(16)


@pytest.fixture
def folder(tmp_path):
    root = tmp_path / "export-keys"
    root.mkdir()
    root.chmod(0o700)
    return root


def listing(folder: Path) -> list[str]:
    return sorted(os.listdir(folder))


def unavailable(call) -> ProtectionUnavailable:
    with pytest.raises(ProtectionUnavailable) as raised:
        call()
    assert raised.value.__cause__ is None and raised.value.__context__ is None
    return raised.value


def test_decision_table_outcomes():
    assert decide(True, True, None) == NORMAL
    assert decide(True, False, None) == REPAIR
    assert decide(False, True, None) == LOSS
    assert decide(False, False, 0) == FIRST_START
    assert decide(False, False, 2) == LOSS
    with pytest.raises(ProtectionUnavailable):
        decide(False, False, None)


def test_first_start_creates_the_key_then_the_marker_with_one_link(folder):
    ring = TokenKeyring(folder, RUN, Witness())
    record = ring.load()
    assert listing(folder) == sorted([KEY_FILE, LOCK_FILE, MARKER_FILE])
    assert (folder / KEY_FILE).stat().st_nlink == 1
    assert record["generation"] == 1 and token_keyring.VERSION.fullmatch(record["active"])
    assert (folder / MARKER_FILE).read_text() == RUN
    assert ring.load() == record  # normal row: use it, no cache, nothing changes


def test_present_key_without_marker_is_used_and_the_marker_repaired(folder):
    ring = TokenKeyring(folder, RUN, Witness())
    record = ring.load()
    (folder / MARKER_FILE).unlink()
    calls = ring.store.calls
    assert ring.load() == record and (folder / MARKER_FILE).exists()
    assert ring.store.calls == calls  # the witness is consulted only when both are absent


@pytest.mark.parametrize("fault", ["mode", "json", "symlink", "run"])
def test_broken_key_file_is_unavailable_and_nothing_is_created(folder, fault):
    ring = TokenKeyring(folder, RUN, Witness())
    ring.load()
    path = folder / KEY_FILE
    if fault == "mode":
        path.chmod(0o644)
    elif fault == "json":
        path.write_text('{"keys": "' + "A" * 40)
    elif fault == "symlink":
        path.unlink()
        path.symlink_to(folder / "elsewhere")
    else:
        value = json.loads(path.read_text())
        path.write_text(json.dumps({**value, "runId": "another-run"}))
    (folder / MARKER_FILE).unlink()
    before = listing(folder)
    error = unavailable(ring.load)
    assert str(error) == "key-custody-broken" and listing(folder) == before


def test_absent_key_with_tokens_left_is_a_loss_and_creates_nothing(folder):
    ring = TokenKeyring(folder, RUN, Witness({version(): 2}))
    assert str(unavailable(ring.load)) == "key-lost" and listing(folder) == []


def test_absent_key_with_marker_present_is_a_loss_and_creates_nothing(folder):
    (folder / MARKER_FILE).write_text(RUN)
    (folder / MARKER_FILE).chmod(0o600)
    ring = TokenKeyring(folder, RUN, Witness())
    assert str(unavailable(ring.load)) == "key-lost" and listing(folder) == [MARKER_FILE]


def test_deleted_key_folder_with_sealed_tokens_left_is_unavailable(folder):
    ring = TokenKeyring(folder, RUN, Witness())
    ring.load()
    for name in os.listdir(folder):
        (folder / name).unlink()
    folder.rmdir()
    assert str(unavailable(ring.load)) == "key-folder-unavailable" and not folder.exists()
    folder.mkdir(mode=0o700)
    ring.store = Witness({version(): 1})
    assert str(unavailable(ring.load)) == "key-lost" and listing(folder) == []


@pytest.mark.parametrize(
    "witness",
    [
        Witness(failure=RuntimeError("database unavailable")),
        Witness(failure=TimeoutError()),
        Witness(raw="not rows"),
        Witness(raw=[{"token_key_version": "u2-v1", "sealed_tokens": 1}]),
        Witness(raw=[{"token_key_version": "u6-" + "a" * 32, "sealed_tokens": 0}]),
        Witness(raw=[{"token_key_version": "u6-" + "a" * 32, "sealed_tokens": True}]),
        Witness(raw=[("u6-" + "a" * 32, 1), ("u6-" + "a" * 32, 1)]),
        Witness(raw=[{"sealed_tokens": 1}]),
    ],
    ids=["error", "timeout", "not-rows", "foreign-version", "zero", "bool", "duplicate", "short"],
)
def test_a_failed_or_malformed_count_is_unavailable_and_creates_no_key(folder, witness):
    ring = TokenKeyring(folder, RUN, witness)
    assert str(unavailable(ring.load)) == "key-count-unavailable"
    assert listing(folder) == []


def test_realm_witness_with_sealed_tokens_refuses_a_new_key(transactions, connect, tmp_path):
    with connect("export") as conn:
        rows.connected(conn)  # the realm now holds at least one sealed token
    folder = tmp_path / "realm-keys"
    folder.mkdir(mode=0o700)
    ring = TokenKeyring(folder, RUN, ExportRepository(transactions, ExportPolicy()))
    assert str(unavailable(ring.load)) == "key-lost" and listing(folder) == []


@pytest.mark.parametrize("shape", ["symlink", "foreign-owner", "0750", "0777", "file"])
def test_key_folder_custody_faults_are_unavailable_and_create_nothing(tmp_path, monkeypatch, shape):
    target = tmp_path / "real-keys"
    target.mkdir(mode=0o700)
    folder = tmp_path / "export-keys"
    if shape == "symlink":
        folder.symlink_to(target)
    elif shape == "file":
        folder.write_text("not a folder")
    else:
        folder.mkdir()
        folder.chmod({"foreign-owner": 0o700, "0750": 0o750, "0777": 0o777}[shape])
    if shape == "foreign-owner":
        owner = os.getuid()
        monkeypatch.setattr(token_keyring, "service_uid", lambda: owner + 1)
    ring = TokenKeyring(folder, RUN, Witness())
    assert str(unavailable(ring.load)) == "key-folder-unavailable"
    assert listing(target) == []
    if folder.is_dir() and not folder.is_symlink():
        assert listing(folder) == []
    with pytest.raises(ProtectionUnavailable):
        with ring.holding():
            pass


def test_two_processes_starting_together_create_one_key_with_one_link(folder, tmp_path):
    child = (
        "import sys, time\n"
        "from pathlib import Path\n"
        "from backend.modules.export.token_keyring import TokenKeyring\n"
        "class Witness:\n"
        "    def token_key_counts(self):\n"
        "        return []\n"
        "root, go = Path(sys.argv[1]), Path(sys.argv[2])\n"
        "deadline = time.monotonic() + 20\n"
        "while not go.exists():\n"
        "    if time.monotonic() > deadline:\n"
        "        sys.exit(3)\n"
        "    time.sleep(0.001)\n"
        "print(TokenKeyring(root, 'u6-race', Witness()).load()['active'])\n"
    )
    go = tmp_path / "go"
    environment = {**os.environ, "PYTHONPATH": str(REPOSITORY)}
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", child, str(folder), str(go)],
            cwd=REPOSITORY,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    time.sleep(0.5)
    go.write_text("go")
    outputs = [process.communicate(timeout=60) for process in processes]
    assert [process.returncode for process in processes] == [0, 0], outputs
    versions = {out.strip() for out, _ in outputs}
    assert len(versions) == 1
    assert (folder / KEY_FILE).stat().st_nlink == 1
    assert not [name for name in os.listdir(folder) if name.startswith(STAGING_PREFIX)]
    assert TokenKeyring(folder, "u6-race", Witness()).load()["active"] in versions


def test_the_loser_of_a_link_race_reads_the_winners_file(folder, monkeypatch):
    ring = TokenKeyring(folder, RUN, Witness())
    winner = ring.load()
    # Re-run the first-start branch as a process that lost the race would.
    monkeypatch.setattr(HeldKeyring, "assess", lambda self: FIRST_START)
    with ring.holding() as held:
        assert held.obtain_first() == winner
    assert (folder / KEY_FILE).stat().st_nlink == 1
    assert not [name for name in os.listdir(folder) if name.startswith(STAGING_PREFIX)]


class FakeClock:
    def __init__(self):
        self.now, self.sleeps = 0.0, []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def test_waiting_lock_retries_then_gives_up_as_unavailable(folder):
    clock = FakeClock()
    policy = ExportPolicy(key_lock_retry_ms=100, key_lock_wait_ms=500)
    ring = TokenKeyring(folder, RUN, Witness(), policy=policy, clock=clock, sleep=clock.sleep)
    with key_custody.exclusive_lock(SETTINGS, folder):
        assert str(unavailable(ring.load)) == "key-lock-unavailable"
    assert clock.sleeps == [0.1] * 5
    assert not (folder / KEY_FILE).exists() and not (folder / MARKER_FILE).exists()
    assert ring.load()["generation"] == 1  # released: the next load succeeds


def test_a_lock_file_with_wrong_custody_fails_at_once(folder):
    clock = FakeClock()
    (folder / LOCK_FILE).write_text("")
    (folder / LOCK_FILE).chmod(0o644)
    ring = TokenKeyring(folder, RUN, Witness(), clock=clock, sleep=clock.sleep)
    assert str(unavailable(ring.load)) == "key-lock-unavailable" and clock.sleeps == []


def test_leftover_staging_files_are_removed_at_the_next_creation_and_rotation(folder):
    stray = [folder / (STAGING_PREFIX + secrets.token_hex(16)) for _ in range(2)]
    for path in stray:
        path.write_text("{}")
        path.chmod(0o600)
    ring = TokenKeyring(folder, RUN, Witness())
    ring.load()
    assert not any(path.exists() for path in stray)
    # A crash after the first-key link leaves a staging name that links the key file.
    linked = folder / (STAGING_PREFIX + secrets.token_hex(16))
    os.link(folder / KEY_FILE, linked)
    unrelated = folder / (STAGING_PREFIX + "not-hex")
    unrelated.write_text("")
    with ring.holding() as held:
        held.rotate()
    assert not linked.exists() and unrelated.exists()
    assert (folder / KEY_FILE).stat().st_nlink == 1


def test_rotate_and_retire_many_times_keep_a_readable_file_past_generation_three(folder):
    ring = TokenKeyring(folder, RUN, Witness())
    first = ring.load()
    retired = []
    for _ in range(6):
        with ring.holding() as held:
            rotation = held.rotate()
        if rotation["retired"]:
            retired.append(rotation["retired"])
    assert len(retired) == 4  # from the third rotation on, the oldest of three retires
    with ring.holding() as held:
        record = held.read()
        held.retire(next(v for v in record["keys"] if v != record["active"]))
    final = key_custody.read_record(SETTINGS, folder, RUN)
    assert final == ring.load() and len(final["keys"]) == 2
    assert first["active"] not in final["keys"]
    # Each rotation, each retirement inside a rotation and the explicit retirement count.
    assert final["generation"] == 1 + 6 + len(retired) + 1
    assert ControlKeyring.custody.generation_max == 3  # U2's range is untouched
    assert len(ring.key(final["active"])) == 32


def test_rotation_with_three_versions_retires_the_oldest_only_at_a_zero_count(folder):
    ring = TokenKeyring(folder, RUN, Witness())
    oldest = ring.load()["active"]
    with ring.holding() as held:
        held.rotate()
        held.rotate()
        three = held.read()
    ring.store = Witness({oldest: 1})
    with ring.holding() as held:
        with pytest.raises(KeyOperationRefused) as refused:
            held.rotate()
    assert refused.value.category == "oldest-version-in-use"
    assert refused.value.counts == {oldest: 1} and ring.load() == three
    ring.store = Witness()
    with ring.holding() as held:
        rotation = held.rotate()
    assert rotation["retired"] == oldest and oldest not in ring.load()["keys"]


def test_retire_refuses_the_active_version_an_absent_one_and_one_in_use(folder):
    ring = TokenKeyring(folder, RUN, Witness())
    old = ring.load()["active"]
    with ring.holding() as held:
        held.rotate()
        active = held.read()["active"]
        for target, category in ((active, "active-version"), (version(), "version-absent")):
            with pytest.raises(KeyOperationRefused) as refused:
                held.retire(target)
            assert refused.value.category == category
    ring.store = Witness({old: 3})
    with ring.holding() as held:
        with pytest.raises(KeyOperationRefused) as refused:
            held.retire(old)
    assert refused.value.counts == {old: 3} and old in ring.load()["keys"]


def test_create_after_loss_refuses_a_first_start_and_a_present_key(folder):
    ring = TokenKeyring(folder, RUN, Witness())
    with ring.holding() as held:
        with pytest.raises(KeyOperationRefused, match="not-a-loss"):
            held.create_after_loss()
    assert not (folder / KEY_FILE).exists()
    ring.load()
    with ring.holding() as held:
        with pytest.raises(KeyOperationRefused, match="not-a-loss"):
            held.create_after_loss()


def test_a_custody_write_failure_is_unavailable_without_its_cause(folder, monkeypatch):
    ring = TokenKeyring(folder, RUN, Witness())
    ring.load()

    def refuse(*_args):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(key_custody.os, "replace", refuse)
    with ring.holding() as held:
        error = unavailable(held.rotate)
    assert str(error) == "key-write-unavailable"


def test_reads_go_to_the_file_every_time(folder):
    ring = TokenKeyring(folder, RUN, Witness())
    first = ring.active_key()
    with TokenKeyring(folder, RUN, Witness()).holding() as held:
        held.rotate()
    second = ring.active_key()
    assert first[0] != second[0] and ring.key(first[0]) == first[1]
    with pytest.raises(ProtectionUnavailable, match="key-version-unavailable"):
        ring.key(version())
