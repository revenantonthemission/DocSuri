"""Cursor signing key custody: creation, exact allocation and refusal."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from backend.modules.discovery.local_http import cursor_key

pytestmark = pytest.mark.u1_component


def test_cursor_key_is_created_once_with_exact_private_allocation(tmp_path: Path):
    key = cursor_key(tmp_path)
    assert len(key) == 32
    path = tmp_path / "search-cursor.key"
    info = path.lstat()
    assert stat.S_IMODE(info.st_mode) == 0o600
    assert info.st_uid == os.getuid()
    # A second assembly reads the same private allocation; it is never rotated.
    assert cursor_key(tmp_path) == key


def test_cursor_key_refuses_a_wrong_allocation(tmp_path: Path):
    path = tmp_path / "search-cursor.key"
    path.write_bytes(b"short")
    with pytest.raises(ValueError, match="exact private allocation"):
        cursor_key(tmp_path)
