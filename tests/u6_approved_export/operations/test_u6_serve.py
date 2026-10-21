"""The owned U6 host: the synthetic assembly, the real composition's refusals, uvicorn."""

import json
import sys
from dataclasses import replace
from types import SimpleNamespace

import pytest
from backend.modules.export.errors import ExportError
from scripts import serve_docsuri_u6 as serve

VALID_SETTINGS = {
    "activationDestinationId": "0123456789abcdef0123456789abcdef",
    "freeTerms": {
        "plan": "free",
        "memberCount": 1,
        "checkedOn": "2026-10-01",
        "publishedLimits": ["free workspace block limit as published"],
    },
}


def write_settings(root, run_id: str) -> None:
    target = root / "real-export.json"
    target.write_text(json.dumps({"runId": run_id, **VALID_SETTINGS}))
    target.chmod(0o600)


def test_serve_assembles_the_owned_synthetic_release(realm):
    app, transport = serve.assemble(realm.root / "environment.json")
    try:
        assert app.state.profile.run_id == realm.run_id
        assert app.state.profile.realm == "approved-export"
        assert app.state.export is not None
        assert transport.certificate.is_file() and transport.key.is_file()
        assert str(transport.certificate).startswith(str(realm.root))
    finally:
        app.state.transactions.close()


def test_the_wrong_realm_is_refused(realm):
    with pytest.raises(ValueError, match="approved-export realm"):
        serve.compose(replace(realm, realm="topics-digests"))
    with pytest.raises(ValueError, match="approved-export realm"):
        serve.compose(replace(realm, database_name="docsuri_u5"), real_export=True)


def test_an_evidence_holding_real_export_is_refused(realm, tmp_path):
    profile = replace(realm, root=tmp_path)
    write_settings(tmp_path, realm.run_id)
    (tmp_path / "coverage-evidence-1.json").write_text("{}")
    with pytest.raises(ExportError) as refused:
        serve.compose(profile, real_export=True)
    assert refused.value.code == "POLICY_UNRESOLVED"
    assert refused.value.current == {"field": "environment"}


def test_the_real_export_refuses_absent_settings(realm, tmp_path):
    with pytest.raises(ExportError) as refused:
        serve.compose(replace(realm, root=tmp_path), real_export=True)
    assert refused.value.current == {"field": "settings-absent"}


def test_the_synthetic_host_refuses_real_export_settings(realm, tmp_path):
    write_settings(tmp_path, realm.run_id)
    with pytest.raises(ValueError, match="real-export settings"):
        serve.compose(replace(realm, root=tmp_path))


def test_an_assembly_of_another_run_is_refused(realm, monkeypatch):
    import backend.u6_host as host

    other = SimpleNamespace(state=SimpleNamespace(profile=SimpleNamespace(run_id="other")))
    monkeypatch.setattr(host, "assemble_u6", lambda profile: other)
    with pytest.raises(ValueError, match="identity mismatch"):
        serve.compose(realm)


def test_main_serves_only_on_the_owned_loopback_listener(realm, monkeypatch):
    calls = {}
    transport = SimpleNamespace(certificate="cert.pem", key="key.pem")
    monkeypatch.setattr(
        serve,
        "assemble",
        lambda path, real_export=False: calls.update(path=path, real=real_export) or ("app", transport),
    )
    monkeypatch.setattr(serve.uvicorn, "run", lambda app, **options: calls.update(app=app, **options))
    monkeypatch.setattr(
        sys, "argv", ["serve", "--environment-file", str(realm.root / "environment.json")]
    )
    serve.main()
    assert calls["real"] is False and calls["app"] == "app"
    assert (calls["host"], calls["port"], calls["workers"]) == ("127.0.0.1", 18099, 1)
    assert (calls["ssl_certfile"], calls["ssl_keyfile"]) == ("cert.pem", "key.pem")
    assert calls["access_log"] is False and calls["proxy_headers"] is False
