"""Tests for the PostgreSQL dependency probe."""

from __future__ import annotations

import json
from unittest.mock import patch

from docsuri_ops.load_probe import PostgresDependencyProbe


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.index = 0

    def fetchone(self):
        if self.index < len(self.rows):
            v = self.rows[self.index]
            self.index += 1
            return v
        return None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


class FakeConnection:
    def __init__(self, rows_by_table):
        self.rows_by_table = rows_by_table

    def execute(self, sql):
        # Extract table name from "SELECT count(*) FROM \"table\""
        import re
        match = re.search(r'FROM\s+"([^"]+)"', sql)
        table = match.group(1) if match else "unknown"
        rows = self.rows_by_table.get(table, [(0,)])
        return FakeCursor(rows)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


def test_probe_returns_counts_for_configured_tables(tmp_path):
    with patch("psycopg.connect") as mock_connect:
        mock_connect.return_value = FakeConnection({"runs": [(42,)], "ledger": [(17,)]})
        probe = PostgresDependencyProbe(
            host="127.0.0.1", port=5432, database="test", user="test",
            tables=("runs", "ledger"),
        )
        counts = probe.counts()
        assert counts == {"runs": 42, "ledger": 17}


def test_probe_handles_missing_table_gracefully(tmp_path):
    with patch("psycopg.connect") as mock_connect:
        mock_connect.return_value = FakeConnection({"runs": [(5,)], "nonexistent": [(0,)]})
        probe = PostgresDependencyProbe(
            host="127.0.0.1", port=5432, database="test", user="test",
            tables=("runs", "nonexistent"),
        )
        counts = probe.counts()
        assert counts == {"runs": 5, "nonexistent": 0}


def test_main_writes_json_output(tmp_path, monkeypatch):
    output = tmp_path / "snapshot.json"
    with patch("psycopg.connect") as mock_connect:
        mock_connect.return_value = FakeConnection({"runs": [(10,)], "ledger": [(20,)]})
        monkeypatch.setattr("sys.stdin.readline", lambda: "password\n")
        from docsuri_ops.load_probe import main
        exit_code = main([
            "--host", "127.0.0.1", "--port", "5432",
            "--database", "test", "--user", "test",
            "--tables", "runs,ledger",
            "--output", str(output),
        ])
    assert exit_code == 0
    assert output.is_file()
    with output.open() as f:
        data = json.load(f)
    assert data == {"runs": 10, "ledger": 20}
    assert oct(output.stat().st_mode & 0o777) == "0o600"
