"""The shared custody helper keeps the built keyring's private-file mechanics (D1)."""

import base64
import json
import os
import secrets
import stat

import pytest
from backend import key_custody
from backend.key_custody import CustodySettings


class CustodyFault(RuntimeError):
    pass


SETTINGS = CustodySettings(
    filename="probe-keyring.json",
    lock_name="probe-keyring.lock",
    marker_name="probe-keyring.initialized",
    staging_prefix=".probe-key-",
    version_pattern=r"p-[0-9a-f]{8}",
    generation_min=1,
    generation_max=5,
    error=CustodyFault,
    lock_message="probe lock custody unavailable",
    custody_message="probe custody unavailable",
    missing_key_message="probe key unavailable",
)
RUN = "probe-run"


def encoded_key(size: int = 32) -> str:
    return base64.b64encode(secrets.token_bytes(size)).decode()


def record(**changes) -> dict:
    value = {
        "runId": RUN,
        "active": "p-00000001",
        "generation": 1,
        "keys": {"p-00000001": encoded_key()},
    }
    value.update(changes)
    return value


@pytest.fixture
def folder(tmp_path):
    root = tmp_path / "keys"
    root.mkdir(mode=0o700)
    return root


def place(folder, content, *, mode=0o600) -> None:
    path = folder / SETTINGS.filename
    path.write_text(content if isinstance(content, str) else json.dumps(content))
    path.chmod(mode)


def test_guarded_read_returns_a_valid_record_and_creates_nothing(folder):
    value = record()
    place(folder, value)
    before = sorted(os.listdir(folder))
    assert key_custody.read_record(SETTINGS, folder, RUN) == value
    assert sorted(os.listdir(folder)) == before


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(record(runId="other-run"), id="run-id"),
        pytest.param(record(active="p-0000000f"), id="active-absent"),
        pytest.param(record(generation=0), id="generation-below"),
        pytest.param(record(generation=6), id="generation-above"),
        pytest.param(record(generation=True), id="generation-bool"),
        pytest.param(record(keys={"x-00000001": encoded_key()}, active="x-00000001"), id="pattern"),
        pytest.param(record(keys={"p-00000001": encoded_key(31)}), id="key-length"),
        pytest.param(record(keys={"p-00000001": "not base64!"}), id="key-encoding"),
        pytest.param(record(keys={}), id="no-version"),
        pytest.param(
            record(keys={f"p-0000000{n}": encoded_key() for n in range(1, 5)}),
            id="too-many-versions",
        ),
        pytest.param({**record(), "extra": 1}, id="extra-field"),
        pytest.param([1, 2], id="not-an-object"),
        pytest.param(
            json.dumps(record())[:-1] + ',"generation":2}', id="duplicate-field"
        ),
        pytest.param("{not json", id="not-json"),
    ],
)
def test_guarded_read_refuses_every_malformed_record(folder, content):
    place(folder, content)
    with pytest.raises(CustodyFault, match="probe custody unavailable") as raised:
        key_custody.read_record(SETTINGS, folder, RUN)
    # The helper keeps the built keyring's chaining; U6 strips it in its own layer.
    assert raised.value.__cause__ is not None


def test_guarded_read_refuses_mode_size_symlink_and_owner(folder, monkeypatch):
    place(folder, record(), mode=0o644)
    with pytest.raises(CustodyFault):
        key_custody.read_record(SETTINGS, folder, RUN)
    place(folder, json.dumps(record()) + " " * 4096)
    with pytest.raises(CustodyFault):
        key_custody.read_record(SETTINGS, folder, RUN)
    real = folder / "real.json"
    real.write_text(json.dumps(record()))
    real.chmod(0o600)
    (folder / SETTINGS.filename).unlink()
    (folder / SETTINGS.filename).symlink_to(real)
    with pytest.raises(CustodyFault):
        key_custody.read_record(SETTINGS, folder, RUN)
    (folder / SETTINGS.filename).unlink()
    place(folder, record())
    owner = os.getuid()
    monkeypatch.setattr(key_custody.os, "getuid", lambda: owner + 1)
    with pytest.raises(CustodyFault):
        key_custody.read_record(SETTINGS, folder, RUN)


def test_missing_file_refuses_without_creating_anything(folder):
    with pytest.raises(CustodyFault):
        key_custody.read_record(SETTINGS, folder, RUN)
    assert os.listdir(folder) == []


def test_non_blocking_lock_refuses_a_second_holder_and_a_bad_lock_file(folder):
    with key_custody.exclusive_lock(SETTINGS, folder):
        with pytest.raises(BlockingIOError):
            with key_custody.exclusive_lock(SETTINGS, folder):
                pass
    # Released: the lock can be taken again, and it is a private regular file.
    with key_custody.exclusive_lock(SETTINGS, folder):
        info = (folder / SETTINGS.lock_name).lstat()
        assert stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600
    (folder / SETTINGS.lock_name).chmod(0o644)
    with pytest.raises(CustodyFault, match="probe lock custody unavailable"):
        with key_custody.exclusive_lock(SETTINGS, folder):
            pass
    (folder / SETTINGS.lock_name).unlink()
    (folder / SETTINGS.lock_name).symlink_to(folder / "elsewhere")
    with pytest.raises(OSError):
        with key_custody.exclusive_lock(SETTINGS, folder):
            pass


def test_staged_write_publishes_by_atomic_replace_and_syncs_the_folder(folder, monkeypatch):
    synced = []
    real_sync = key_custody.sync_folder
    monkeypatch.setattr(
        key_custody, "sync_folder", lambda root: (synced.append(root), real_sync(root))
    )
    place(folder, record())
    before = (folder / SETTINGS.filename).stat().st_ino
    value = record(generation=2)
    key_custody.write(SETTINGS, folder, value)
    path = folder / SETTINGS.filename
    assert json.loads(path.read_text()) == value
    assert stat.S_IMODE(path.stat().st_mode) == 0o600 and path.stat().st_ino != before
    assert synced == [folder]
    assert os.listdir(folder) == [SETTINGS.filename]


def test_failed_publish_removes_its_staging_file_and_keeps_the_old_record(folder, monkeypatch):
    original = record()
    place(folder, original)

    def refuse(source, target):
        raise OSError("simulated publish failure")

    monkeypatch.setattr(key_custody.os, "replace", refuse)
    with pytest.raises(OSError):
        key_custody.write(SETTINGS, folder, record(generation=2))
    assert os.listdir(folder) == [SETTINGS.filename]
    assert key_custody.read_record(SETTINGS, folder, RUN) == original


def test_stage_is_exclusive_private_synced_and_cleans_up_a_failed_dump(folder):
    staging = key_custody.stage(SETTINGS, folder, record())
    assert staging.name.startswith(SETTINGS.staging_prefix)
    assert stat.S_IMODE(staging.stat().st_mode) == 0o600
    assert json.loads(staging.read_text())["runId"] == RUN
    staging.unlink()
    with pytest.raises(TypeError):
        key_custody.stage(SETTINGS, folder, {"unserialisable": object()})
    assert os.listdir(folder) == []


def test_marker_is_created_exclusively_and_synced(folder, monkeypatch):
    synced = []
    monkeypatch.setattr(key_custody, "sync_folder", synced.append)
    key_custody.create_marker(SETTINGS, folder, RUN)
    marker = folder / SETTINGS.marker_name
    assert marker.read_text() == RUN and stat.S_IMODE(marker.stat().st_mode) == 0o600
    assert synced == [folder]
    with pytest.raises(FileExistsError):
        key_custody.create_marker(SETTINGS, folder, "another-run")
    assert marker.read_text() == RUN


def test_retained_key_refuses_an_absent_version():
    value = record()
    assert len(key_custody.retained_key(SETTINGS, value, "p-00000001")) == 32
    with pytest.raises(CustodyFault, match="probe key unavailable"):
        key_custody.retained_key(SETTINGS, value, "p-00000002")


@pytest.mark.parametrize(
    "change",
    [
        {"filename": "a/b"},
        {"marker_name": ".."},
        {"generation_min": 0},
        {"generation_min": 4, "generation_max": 3},
        {"max_versions": 0},
        {"max_bytes": 0},
    ],
)
def test_settings_refuse_unsafe_configuration(change):
    values = {**SETTINGS.__dict__, **change}
    with pytest.raises(ValueError):
        CustodySettings(**values)
