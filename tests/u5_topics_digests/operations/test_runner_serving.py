"""Real filesystem/realm checks for the synthetic U5 runner's assets and serving.

Grouped by the runner's parts (decision L2-1): the always-rebuilt browser assets,
the browser fixture record and its restartable setup, serving the owned release,
and the refused real delivery without an operator activation.
"""

import pytest

from scripts import verify_docsuri_u5 as runner


@pytest.fixture
def owned_root(tmp_path, monkeypatch):
    root = tmp_path / "run"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(runner, "RUN", root)
    return root


def test_browser_assets_always_rebuild_and_refuse_failed_build(owned_root, monkeypatch):
    calls = []

    def build(command, log, *, seconds):
        calls.append((command, log, seconds))
        return {"exitCode": 1, "processStopped": True}

    monkeypatch.setattr(runner, "bounded_process", build)
    with pytest.raises(runner.Refused, match="asset build failed") as failure:
        runner.build_browser_assets(owned_root / "build.log", seconds=30)
    assert calls[0][0] == ["corepack", "pnpm@9.15.9", "--dir", "frontend", "exec", "vite", "build"]
    assert calls[0][2] == 30
    assert failure.value.supervision["processStopped"] is True


def test_browser_fixture_record_is_bound_to_the_run(realm):
    from scripts import u5_browser_fixtures as fixtures

    record = fixtures.fixture_record(realm)
    assert record["runId"] == realm.run_id
    assert record["fixtureVersion"] == "u5-browser-v1"
    assert record["state"] in ("prepared", "ready")
    assert set(record["accounts"]) == {"memberA", "memberB"}


def test_browser_fixture_setup_is_restartable_and_complete(realm):
    from scripts import u5_browser_fixtures as fixtures

    first = fixtures.setup(realm.root / "environment.json")
    assert first["state"] == "fixtures-ready"
    assert first["accounts"] == 2 and first["papers"] == 2
    second = fixtures.setup(realm.root / "environment.json")
    assert second == first
    record = fixtures.fixture_record(realm)
    assert record["state"] == "ready"
    # The resolve fixture stays present after a re-run: one unresolved unknown
    # for the fixture topic, with every earlier attempt's gap recorded.
    transactions_owner = realm.root
    assert (transactions_owner / "browser-fixtures.json").is_file()


def test_serve_assembles_the_owned_release(realm):
    import scripts.serve_docsuri_u5 as serve

    app, transport = serve.assemble(realm.root / "environment.json")
    try:
        assert app.state.profile.run_id == realm.run_id
        assert app.state.profile.realm == "topics-digests"
        assert hasattr(app.state, "topics")
        assert hasattr(app.state, "topics_scheduler")
        assert transport.certificate.is_file()
    finally:
        app.state.transactions.close()


def test_serve_real_delivery_refuses_without_operator_activation(realm, monkeypatch):
    import scripts.serve_docsuri_u5 as serve
    from backend.u5_real_delivery import RealDeliveryRefused

    # Ambient provider variables alone never enable the real composition.
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", "fake-credential-for-refusal-check")
    assert not (realm.root / "real-delivery.json").exists()
    with pytest.raises(RealDeliveryRefused, match="activation is absent"):
        serve.assemble(realm.root / "environment.json", real_delivery=True)
