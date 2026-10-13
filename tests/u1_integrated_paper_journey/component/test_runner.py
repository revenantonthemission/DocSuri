"""Narrow failure injection for orchestration; no fake business readiness."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

import pytest

SPEC = importlib.util.spec_from_file_location(
    "u1_runner", Path(__file__).resolve().parents[3] / "scripts/verify_docsuri_u1.py"
)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)
pytestmark = pytest.mark.u1_component


def test_clean_environment_drops_provider_and_database_credentials(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    assert "DATABASE_URL" not in runner.clean_environment()
    assert "OPENAI_API_KEY" not in runner.clean_environment()


def test_finite_allocation_refuses_low_disk(monkeypatch):
    monkeypatch.setattr(
        runner.shutil, "disk_usage", lambda _: type("Usage", (), {"free": 11 * runner.GIB})()
    )
    with pytest.raises(runner.Refused, match="headroom"):
        runner.headroom()


def test_repeat_setup_accounts_for_installed_bytes_without_lowering_reserves(monkeypatch):
    monkeypatch.setattr(
        runner,
        "require",
        lambda args: subprocess.CompletedProcess(
            args, 0, stdout=f"{runner.GIB // 1024}\tmeasured-build\n", stderr=""
        ),
    )
    monkeypatch.setattr(
        runner.shutil, "disk_usage", lambda _: type("Usage", (), {"free": 11 * runner.GIB})()
    )
    runner.headroom(existing=True)
    monkeypatch.setattr(
        runner.shutil, "disk_usage", lambda _: type("Usage", (), {"free": 11 * runner.GIB - 1})()
    )
    with pytest.raises(runner.Refused, match="headroom"):
        runner.headroom(existing=True)
    monkeypatch.setattr(
        runner,
        "require",
        lambda args: subprocess.CompletedProcess(
            args, 0, stdout=f"{3 * runner.GIB // 1024}\toversized-build\n", stderr=""
        ),
    )
    with pytest.raises(runner.Refused, match="exceeds 2 GiB"):
        runner.headroom(existing=True)


def test_coverage_refuses_absent_source_inventory():
    with pytest.raises(runner.Refused, match="source inventory"):
        runner.phase_commands("coverage")


def test_repeat_setup_without_build_paths_cannot_credit_working_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "ROOT", tmp_path)

    def unexpected_command(*args, **kwargs):
        pytest.fail("no build paths should mean no du invocation")

    monkeypatch.setattr(runner, "require", unexpected_command)
    monkeypatch.setattr(
        runner.shutil, "disk_usage", lambda _: type("Usage", (), {"free": 11 * runner.GIB})()
    )
    with pytest.raises(runner.Refused, match="headroom"):
        runner.headroom(existing=True)
    monkeypatch.setattr(
        runner.shutil, "disk_usage", lambda _: type("Usage", (), {"free": 12 * runner.GIB})()
    )
    runner.headroom(existing=True)


def test_collection_is_exact_component_scope():
    collect, execute, cwd = runner.phase_commands("component")
    assert str(runner.ROOT / "tests/u1_integrated_paper_journey/component") in collect
    assert "--collect-only" in collect and "--collect-only" not in execute
    assert collect[collect.index("-m") + 1] == "pytest"
    assert "u1_component" in collect
    assert cwd == runner.ROOT


@pytest.mark.parametrize(
    "collection_exit,collected,counts,changing,expected",
    [
        (0, 0, {}, False, "collection failed or empty"),
        (2, 3, {}, False, "collection failed or empty"),
        (0, 3, {"tests": "3", "skipped": "3"}, False, "required cases skipped"),
        (0, 3, {"tests": "3", "skipped": "1"}, False, "required cases skipped"),
        (0, 3, {"tests": "3"}, True, "source changed"),
    ],
)
def test_failed_evidence_cannot_report_success(
    monkeypatch, tmp_path, collection_exit, collected, counts, changing, expected
):
    # All file publication and commands are replaced within this fault test;
    # the real owned environment remains untouched.
    monkeypatch.setattr(runner, "RUN", tmp_path)
    reports = []
    monkeypatch.setattr(runner, "private_json", lambda path, value: reports.append(value))
    monkeypatch.setattr(runner, "phase_commands", lambda _: (["collect"], ["execute"], runner.ROOT))
    calls = iter(["before", "after" if changing else "before"])
    monkeypatch.setattr(runner, "source_identity", lambda: {"sha256": next(calls)})
    monkeypatch.setattr(
        runner,
        "command",
        lambda args, **kwargs: subprocess.CompletedProcess(
            args,
            collection_exit if args == ["collect"] else 0,
            f"{collected} tests collected" if args == ["collect"] else "",
            "",
        ),
    )
    element = ET.Element("testsuites")
    ET.SubElement(element, "testsuite", counts)
    monkeypatch.setattr(runner.ET, "parse", lambda _: ET.ElementTree(element))
    with pytest.raises(runner.Refused, match=expected):
        runner.run_phase("component", {"applicationPort": 18039}, tmp_path / "environment.json")
    assert reports and reports[0]["collected"] == collected
