"""Private U2 TLS bootstrap and real pinned handshake; no shared store access."""

import hashlib
import json
import os
import socket
import ssl
import stat
import threading
import time
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI

from backend.local_profile import LocalProfile
from docsuri_ops.local_transport import inspect_transport, prepare_transport
from scripts import prepare_docsuri_u2_transport, serve_docsuri_u2

pytestmark = pytest.mark.u2_operations


@pytest.fixture(scope="session", autouse=True)
def exclusive_environment():
    """These tmp-path crypto tests do not acquire or use the shared DB fixture."""
    yield


def selected_profile(root: Path) -> LocalProfile:
    return LocalProfile(
        root, "docsuri-u2-0123456789abcdef", "https://127.0.0.1:18049", 15449,
        time.time() + 3600, "docsuri_u2", "account-controls",
    )


def test_exact_certificate_replay_preserves_key_and_u1_material(tmp_path):
    selected = selected_profile(tmp_path)
    legacy = replace(selected, realm="journey", origin="https://127.0.0.1:18039",
        database_name="docsuri_u1_journey")
    u1 = prepare_transport(legacy)
    u1_bytes = (u1.certificate.read_bytes(), u1.key.read_bytes())
    first = prepare_transport(selected)
    first_bytes = (first.certificate.read_bytes(), first.key.read_bytes())
    assert first == prepare_transport(selected) == inspect_transport(selected)
    assert first.certificate.name == "account-controls-tls.crt"
    assert first.key.name == "account-controls-tls.key"
    assert first_bytes == (first.certificate.read_bytes(), first.key.read_bytes())
    assert u1_bytes == (u1.certificate.read_bytes(), u1.key.read_bytes())
    assert u1.certificate.name == "journey-tls.crt"
    for suffix in ("crt", "key", "json", "lock"):
        path = tmp_path / f"account-controls-tls.{suffix}"
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    certificate = x509.load_pem_x509_certificate(first.certificate.read_bytes())
    assert int(certificate.not_valid_after_utc.timestamp()) == int(selected.expires_at)


@pytest.mark.parametrize("change", [
    {"origin": "https://localhost:18049"},
    {"origin": "http://127.0.0.1:18049"},
    {"origin": "https://127.0.0.1:18039"},
    {"origin": "https://0.0.0.0:18049"},
    {"realm": "journey"},
    {"database_name": "docsuri_u1_journey"},
])
def test_foreign_transport_binding_is_refused_before_material(tmp_path, change):
    selected = replace(selected_profile(tmp_path), **change)
    for action in (prepare_transport, inspect_transport):
        with pytest.raises(ValueError, match="explicit owned realm"):
            action(selected)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("lifetime", [-1, 86401])
def test_expired_or_unbounded_transport_lifetime_refuses(tmp_path, lifetime):
    selected = replace(selected_profile(tmp_path), expires_at=time.time() + lifetime)
    with pytest.raises(ValueError, match="retention"):
        prepare_transport(selected)
    assert not (tmp_path / "account-controls-tls.key").exists()


@pytest.mark.parametrize("field,value", [
    ("runId", "docsuri-u2-ffffffffffffffff"),
    ("origin", "https://127.0.0.1:18039"),
    ("database", "docsuri_u1_journey"),
    ("certificateSha256", "0" * 64),
    ("expiresAt", 0),
])
def test_changed_manifest_binding_never_rotates_existing_key(tmp_path, field, value):
    selected = selected_profile(tmp_path)
    original = prepare_transport(selected)
    original_key = original.key.read_bytes()
    manifest = tmp_path / "account-controls-tls.json"
    record = json.loads(manifest.read_bytes())
    record[field] = value
    manifest.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="binding"):
        prepare_transport(selected)
    assert original.key.read_bytes() == original_key


def test_mismatched_private_key_refuses(tmp_path):
    selected = selected_profile(tmp_path)
    transport = prepare_transport(selected)
    substitute = ec.generate_private_key(ec.SECP256R1())
    transport.key.write_bytes(substitute.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    with pytest.raises(ValueError, match="binding"):
        inspect_transport(selected)


@pytest.mark.parametrize("substitution", ["symlink", "hardlink", "fifo", "mode"])
def test_unsafe_key_custody_refuses_without_blocking(tmp_path, substitution):
    selected = selected_profile(tmp_path)
    transport = prepare_transport(selected)
    if substitution == "mode":
        transport.key.chmod(0o644)
    else:
        original = tmp_path / "original-key"
        transport.key.rename(original)
        if substitution == "symlink":
            transport.key.symlink_to(original)
        elif substitution == "hardlink":
            os.link(original, transport.key)
        else:
            os.mkfifo(transport.key, 0o600)
    with pytest.raises((ValueError, OSError)):
        inspect_transport(selected)


def test_partial_provisioning_preserves_surviving_certificate(tmp_path):
    selected = selected_profile(tmp_path)
    transport = prepare_transport(selected)
    before = transport.certificate.read_bytes()
    (tmp_path / "account-controls-tls.json").unlink()
    with pytest.raises(ValueError, match="partial"):
        prepare_transport(selected)
    assert transport.certificate.read_bytes() == before


def test_directory_flush_failure_cannot_acknowledge_then_retry_preserves_key(tmp_path, monkeypatch):
    selected = selected_profile(tmp_path)
    fsync = os.fsync

    def fail_directory(descriptor):
        if stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise OSError("injected directory flush failure")
        fsync(descriptor)

    with monkeypatch.context() as patch:
        patch.setattr(os, "fsync", fail_directory)
        with pytest.raises(OSError, match="flush failure"):
            prepare_transport(selected)
    original_key = (tmp_path / "account-controls-tls.key").read_bytes()
    transport = prepare_transport(selected)
    assert original_key == transport.key.read_bytes()


@pytest.mark.parametrize("script", [prepare_docsuri_u2_transport, serve_docsuri_u2])
def test_cli_requires_explicit_manifest_and_rejects_other_unit(tmp_path, monkeypatch, script):
    monkeypatch.setattr("sys.argv", [script.__file__])
    with pytest.raises(SystemExit) as omitted:
        script.main()
    assert omitted.value.code == 2
    legacy = replace(selected_profile(tmp_path), realm="journey", database_name="docsuri_u1_journey")
    monkeypatch.setattr(LocalProfile, "load", lambda path: legacy)
    monkeypatch.setattr("sys.argv", [script.__file__, "--environment-file", str(tmp_path / "environment.json")])
    with pytest.raises(ValueError, match="account-controls"):
        script.main()


def test_prepare_cli_reports_only_public_transport_evidence(tmp_path, monkeypatch, capsys):
    selected = selected_profile(tmp_path)
    manifest = tmp_path / "environment.json"
    paths = []

    def load(path):
        paths.append(path)
        return selected

    monkeypatch.setattr(LocalProfile, "load", load)
    monkeypatch.setattr("sys.argv", [prepare_docsuri_u2_transport.__file__, "--environment-file", str(manifest)])
    prepare_docsuri_u2_transport.main()
    evidence = json.loads(capsys.readouterr().out)
    assert paths == [manifest]
    assert evidence == {"origin": selected.origin,
        "certificateSha256": inspect_transport(selected).certificate_sha256,
        "trustStoreModified": False}


def test_serve_cli_uses_one_bounded_loopback_listener_without_proxy_or_access_logs(tmp_path, monkeypatch):
    selected = selected_profile(tmp_path)
    transport = prepare_transport(selected)
    app = object()
    received = []
    monkeypatch.setattr(LocalProfile, "load", lambda path: selected)
    monkeypatch.setattr(serve_docsuri_u2, "assemble_journey", lambda profile: app)
    monkeypatch.setattr(serve_docsuri_u2.uvicorn, "run", lambda *args, **kwargs: received.append((args, kwargs)))
    monkeypatch.setattr("sys.argv", [serve_docsuri_u2.__file__, "--environment-file", str(tmp_path / "environment.json")])
    serve_docsuri_u2.main()
    assert received == [((app,), {
        "host": "127.0.0.1", "port": 18049, "workers": 1,
        "ssl_certfile": str(transport.certificate), "ssl_keyfile": str(transport.key),
        "access_log": False, "proxy_headers": False, "limit_concurrency": 32, "backlog": 16,
        "timeout_keep_alive": 5, "timeout_graceful_shutdown": 10,
    })]


def test_real_tls_handshake_is_certificate_and_hostname_bound(tmp_path):
    transport = prepare_transport(selected_profile(tmp_path))
    app = FastAPI()

    @app.get("/ready")
    def ready():
        return {"fixture": "transport-only"}

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(4)
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False,
        proxy_headers=False, limit_concurrency=10, timeout_keep_alive=5,
        timeout_graceful_shutdown=1, ssl_certfile=str(transport.certificate),
        ssl_keyfile=str(transport.key)))
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started
        port = listener.getsockname()[1]
        context = ssl.create_default_context(cafile=str(transport.certificate))
        with socket.create_connection(("127.0.0.1", port), timeout=3) as connection:
            with context.wrap_socket(connection, server_hostname="127.0.0.1") as tls:
                assert hashlib.sha256(tls.getpeercert(binary_form=True)).hexdigest() == transport.certificate_sha256
        with socket.create_connection(("127.0.0.1", port), timeout=3) as connection:
            with pytest.raises(ssl.SSLCertVerificationError):
                context.wrap_socket(connection, server_hostname="wrong.fixture.invalid")
        with httpx.Client(verify=context, trust_env=False, timeout=3) as client:
            assert client.get(f"https://127.0.0.1:{port}/ready").json() == {"fixture": "transport-only"}
    finally:
        server.should_exit = True
        thread.join(5)
        listener.close()
        assert not thread.is_alive()
