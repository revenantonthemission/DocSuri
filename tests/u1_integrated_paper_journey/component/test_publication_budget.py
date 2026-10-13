"""Publication evidence remains bounded and immutable on refused allocation."""

import hashlib
import json
import os
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from scripts import publish_docsuri_u1_papers as publisher

pytestmark = pytest.mark.u1_component


def test_directory_enumeration_stops_before_materializing_unbounded_entries(tmp_path, monkeypatch):
    visited = []

    @contextmanager
    def polluted_directory(_):
        def entries():
            for index in range(1000000):
                visited.append(index)
                yield SimpleNamespace(name=f"unrelated-{index}")

        yield entries()

    monkeypatch.setattr(publisher.os, "scandir", polluted_directory)
    with pytest.raises(ValueError, match="directory inventory"):
        publisher.reserve_evidence(tmp_path, {"attemptCount": 0})
    assert len(visited) == publisher.DIRECTORY_ENTRIES + 1


def attempt(root, number, size=None):
    path = root / f"corpus-publication-attempt-{number}.json"
    raw = json.dumps({"startedAt": 1, "status": "published", "sourceIdentity": {}}).encode()
    if size is not None:
        raw += b" " * (size - len(raw))
    path.write_bytes(raw)
    path.chmod(0o600)
    return path, hashlib.sha256(raw).hexdigest()


def record(paths):
    return {
        "attemptCount": len(paths),
        "latestAttempt": {"file": paths[-1][0].name, "sha256": paths[-1][1]},
    }


def test_sixteen_small_attempts_leave_reserved_capacity(tmp_path):
    paths = [attempt(tmp_path, i) for i in range(16)]
    before = {p.name: p.read_bytes() for p, _ in paths}
    with publisher.publication_lock(tmp_path):
        occupied = publisher.reserve_evidence(tmp_path, record(paths))
    assert occupied == sum(map(len, before.values()))
    assert before == {p.name: p.read_bytes() for p, _ in paths}


def test_full_byte_allocation_refuses_without_changing_evidence(tmp_path):
    paths = [attempt(tmp_path, i, publisher.ATTEMPT_BYTES) for i in range(16)]
    before = {p.name: digest for p, digest in paths}
    with publisher.publication_lock(tmp_path), pytest.raises(ValueError, match="exhausted"):
        publisher.reserve_evidence(tmp_path, record(paths))
    assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p, _ in paths}


def test_reserve_requires_a_whole_result_even_with_one_byte_deficit(tmp_path):
    paths = [attempt(tmp_path, i, publisher.ATTEMPT_BYTES) for i in range(15)]
    paths.append(attempt(tmp_path, 15))
    with pytest.raises(ValueError, match="exhausted"):
        publisher.reserve_evidence(tmp_path, record(paths))


def test_file_count_is_finite_even_for_tiny_attempts(tmp_path):
    paths = [attempt(tmp_path, i) for i in range(64)]
    with pytest.raises(ValueError, match="count"):
        publisher.reserve_evidence(tmp_path, record(paths))


def test_correctly_hashed_running_attempt_requires_explicit_recovery(tmp_path):
    path, _ = attempt(tmp_path, 1)
    raw = json.dumps({"startedAt": 1, "status": "running", "sourceIdentity": {}}).encode()
    path.write_bytes(raw)
    current = record([(path, hashlib.sha256(raw).hexdigest())])
    with pytest.raises(ValueError, match="unrecognized"):
        publisher.reserve_evidence(tmp_path, current)
    assert path.read_bytes() == raw


@pytest.mark.parametrize("fault", ["changed", "orphan", "pending", "symlink", "alias"])
def test_unexplained_or_changed_evidence_refuses(tmp_path, fault):
    paths = [attempt(tmp_path, 1)]
    current = record(paths)
    if fault == "changed":
        paths[0][0].write_bytes(paths[0][0].read_bytes() + b" ")
    elif fault == "orphan":
        attempt(tmp_path, 2)
    elif fault == "pending":
        paths[0][0].rename(paths[0][0].with_suffix(".json.pending"))
    elif fault == "symlink":
        original = paths[0][0].rename(tmp_path / "original")
        paths[0][0].symlink_to(original)
    else:
        os.link(paths[0][0], tmp_path / "alias")
    with pytest.raises((ValueError, OSError)):
        publisher.reserve_evidence(tmp_path, current)


def test_lock_prevents_overlapping_admission_and_releases_after_failure(tmp_path):
    with pytest.raises(RuntimeError):
        with publisher.publication_lock(tmp_path):
            with pytest.raises(BlockingIOError):
                with publisher.publication_lock(tmp_path):
                    pytest.fail("concurrent publication admitted")
            raise RuntimeError("injected publication failure")
    with publisher.publication_lock(tmp_path):
        assert publisher.reserve_evidence(tmp_path, {"attemptCount": 0}) == 0
