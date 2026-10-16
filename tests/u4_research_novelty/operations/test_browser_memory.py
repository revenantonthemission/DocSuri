import json
import shutil

from scripts import verify_docsuri_u4 as runner


def test_browser_coordinator_and_worker_inherit_tighter_heap(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUN", tmp_path)
    monkeypatch.setattr(runner, "process_rss", lambda *_: 1)
    log = tmp_path / "host.log"
    log.write_text("")
    log.chmod(0o600)
    node = shutil.which("node")
    assert node, "installed Node runtime is required"

    class Companion:
        pid = 1

        def poll(self):
            return None

    script = (
        "const v8=require('node:v8');const cp=require('node:child_process');"
        "const child=cp.execFileSync(process.execPath,['-e',"
        "'console.log(require(\"node:v8\").getHeapStatistics().heap_size_limit)'],"
        "{encoding:'utf8'});console.log(JSON.stringify({"
        "options:process.env.NODE_OPTIONS,main:v8.getHeapStatistics().heap_size_limit,"
        "child:Number(child)}));"
    )
    outcome = runner.bounded_process(
        [node, "-e", script], tmp_path / "node.log", seconds=5,
        companion=Companion(), companion_log=log,
    )
    assert outcome["exitCode"] == 0 and outcome["processStopped"]
    measured = json.loads((tmp_path / "node.log").read_text())
    assert measured["options"] == "--max-old-space-size=128 --max-semi-space-size=8"
    assert 128 * 1024**2 <= measured["main"] <= 176 * 1024**2
    assert measured["child"] == measured["main"]
    assert runner.MAX_RSS == 1024**3


def test_installed_browser_config_keeps_all_journeys_and_renderer_bound():
    config = (runner.ROOT / "frontend/playwright.u4-research.config.ts").read_text()
    assert "--js-flags=--max-old-space-size=128" in config
    assert "--max-semi-space-size=8" in config
    assert "workers: 1" in config and "globalTimeout: 300_000" in config
    assert "testDir: './e2e/u4-research-novelty'" in config
    assert "retries: 0" in config
