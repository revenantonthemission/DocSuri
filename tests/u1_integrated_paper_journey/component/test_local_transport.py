"""Protected certificate custody and actual pinned TLS, without global trust."""

import hashlib
import json
import os
import socket
import ssl
import stat
import threading
import time
from dataclasses import replace

import httpx
import pytest
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.local_profile import LocalProfile
from docsuri_ops.local_transport import inspect_transport, prepare_transport

pytestmark = pytest.mark.u1_component


def profile(root):
    return LocalProfile(
        root,
        "owned-transport-test",
        "https://127.0.0.1:18039",
        15439,
        time.time() + 3600,
        "docsuri_u1_journey",
        "journey",
    )


def test_transport_replays_exact_cert_without_key_or_trust_rotation(tmp_path):
    selected = profile(tmp_path)
    initial = prepare_transport(selected)
    certificate = initial.certificate.read_bytes()
    key_hash = hashlib.sha256(initial.key.read_bytes()).hexdigest()
    assert prepare_transport(selected) == initial == inspect_transport(selected)
    assert initial.certificate.read_bytes() == certificate
    assert hashlib.sha256(initial.key.read_bytes()).hexdigest() == key_hash
    assert initial.key.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("change", ["origin", "realm", "expiry"])
def test_wrong_or_expired_transport_profile_refuses(tmp_path, change):
    selected = profile(tmp_path)
    if change == "origin":
        selected = replace(selected, origin="http://127.0.0.1:18039")
    elif change == "realm":
        selected = replace(selected, realm="diagnostic")
    else:
        selected = replace(selected, expires_at=time.time() - 1)
    with pytest.raises(ValueError):
        prepare_transport(selected)
    assert not (tmp_path / "journey-tls.key").exists()


def test_changed_manifest_and_partial_material_are_never_adopted(tmp_path):
    selected = profile(tmp_path)
    transport = prepare_transport(selected)
    path = tmp_path / "journey-tls.json"
    raw = json.loads(path.read_bytes())
    raw["certificateSha256"] = "0" * 64
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="binding"):
        prepare_transport(selected)
    path.unlink()
    before = transport.certificate.read_bytes()
    with pytest.raises(ValueError, match="partial"):
        prepare_transport(selected)
    assert transport.certificate.read_bytes() == before


def test_directory_sync_failure_does_not_acknowledge_and_retry_preserves_key(tmp_path, monkeypatch):
    selected = profile(tmp_path)
    original_sync = os.fsync

    def fail_directory(descriptor):
        if stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise OSError("injected directory sync failure")
        original_sync(descriptor)

    with monkeypatch.context() as patch:
        patch.setattr(os, "fsync", fail_directory)
        with pytest.raises(OSError, match="directory sync"):
            prepare_transport(selected)
    key_hash = hashlib.sha256((tmp_path / "journey-tls.key").read_bytes()).hexdigest()
    transport = prepare_transport(selected)
    assert hashlib.sha256(transport.key.read_bytes()).hexdigest() == key_hash


def test_fifo_and_aliased_private_key_refuse_without_blocking(tmp_path):
    selected = profile(tmp_path)
    transport = prepare_transport(selected)
    original = tmp_path / "original-key"
    transport.key.rename(original)
    os.mkfifo(transport.key, 0o600)
    with pytest.raises(ValueError, match="regular"):
        inspect_transport(selected)
    transport.key.unlink()
    os.link(original, transport.key)
    with pytest.raises(ValueError, match="aliased"):
        inspect_transport(selected)


def test_actual_tls_checks_served_fingerprint_host_and_secure_cookie(tmp_path):
    transport = prepare_transport(profile(tmp_path))
    app = FastAPI()

    @app.get("/")
    def probe(request: Request):
        response = JSONResponse(
            {"returned": request.cookies.get("session_id") == "synthetic-probe"}
        )
        response.set_cookie(
            "session_id", "synthetic-probe", secure=True, httponly=True, samesite="strict"
        )
        return response

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(4)
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            log_level="error",
            ssl_certfile=str(transport.certificate),
            ssl_keyfile=str(transport.key),
        )
    )
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.01)
    try:
        assert server.started
        port = listener.getsockname()[1]
        context = ssl.create_default_context(cafile=str(transport.certificate))
        with socket.create_connection(("127.0.0.1", port), timeout=3) as connection:
            with context.wrap_socket(connection, server_hostname="127.0.0.1") as tls:
                assert (
                    hashlib.sha256(tls.getpeercert(binary_form=True)).hexdigest()
                    == transport.certificate_sha256
                )
        with socket.create_connection(("127.0.0.1", port), timeout=3) as connection:
            with pytest.raises(ssl.SSLCertVerificationError):
                context.wrap_socket(connection, server_hostname="wrong.example")
        with httpx.Client(
            base_url=f"https://127.0.0.1:{port}", verify=context, timeout=3, trust_env=False
        ) as client:
            first = client.get("/")
            assert not first.json()["returned"]
            assert all(
                value in first.headers["set-cookie"]
                for value in ("Secure", "HttpOnly", "SameSite=strict")
            )
            assert client.get("/").json()["returned"]
    finally:
        server.should_exit = True
        thread.join(5)
        listener.close()
        assert not thread.is_alive()
