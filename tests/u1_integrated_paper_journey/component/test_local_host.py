"""Mounted framework proof; transport probes do not establish account/job readiness."""
from __future__ import annotations

import os
from pathlib import Path
import socket
import threading
import time

import httpx
import pytest
from fastapi.responses import StreamingResponse
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
import uvicorn

from backend.app import create_app
from backend.local_profile import LocalProfile

pytestmark = pytest.mark.u1_component


@pytest.fixture(scope='module')
def mounted():
    path = Path(os.environ['DOCSURI_U1_ENVIRONMENT_FILE'])
    app = create_app(local_environment=path)

    async def transport(request: Request):
        # Explicit framework-only probe: no claim of authenticated identity.
        if request.query_params.get('stream'):
            return StreamingResponse(iter([b'id: 1\nevent: probe\ndata: {"transport":true}\n\n']),
                                     media_type='text/event-stream')
        response = JSONResponse({'cookieReturned': request.cookies.get('transport_probe') == 'probe'})
        response.set_cookie('transport_probe', 'probe', httponly=True, samesite='strict')
        return response

    app.router.routes.insert(0, Route('/__transport_probe', transport))
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level='error'))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(.01)
    assert server.started, 'mounted server did not start'
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{listener.getsockname()[1]}', timeout=5) as client:
            yield client
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
        assert not thread.is_alive()


def test_explicit_profile_uses_owned_manifest():
    profile = LocalProfile.load(Path(os.environ['DOCSURI_U1_ENVIRONMENT_FILE']))
    assert profile.root == Path('/tmp/docsuri-u1-run').resolve()
    assert profile.origin == 'http://127.0.0.1:18039'


def test_profile_rejects_other_directory():
    with pytest.raises(ValueError, match='explicit owned'):
        LocalProfile.load(Path('/tmp/not-the-owned-manifest.json'))


def test_liveness_does_not_claim_readiness(mounted):
    assert mounted.get('/health/live').json()['process'] == 'alive'
    response = mounted.get('/health/ready')
    assert response.status_code == 503
    assert response.json()['ready'] is False
    assert len(response.json()['missing']) == 8


def test_static_build_supports_deep_link(mounted):
    response = mounted.get('/papers/1706.03762')
    assert response.status_code == 200
    assert '<html lang="ko">' in response.text
    assert '/assets/' in response.text
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-content-type-options'] == 'nosniff'


def test_unknown_api_never_returns_static_success(mounted):
    response = mounted.get('/api/not-implemented')
    assert response.status_code == 503
    assert response.json()['code'] == 'NOT_READY'


def test_host_and_origin_boundary_with_positive_control(mounted):
    assert mounted.get('/health/live', headers={'Host': 'evil.example'}).status_code == 400
    assert mounted.get('/health/live', headers={'Origin': 'https://evil.example'}).status_code == 403
    assert mounted.get('/health/live', headers={'Origin': 'http://127.0.0.1:18039'}).status_code == 200


def test_actual_http_cookie_round_trip(mounted):
    first = mounted.get('/__transport_probe')
    assert first.json()['cookieReturned'] is False
    assert 'HttpOnly' in first.headers['set-cookie']
    assert 'SameSite=strict' in first.headers['set-cookie']
    assert mounted.get('/__transport_probe').json()['cookieReturned'] is True


def test_actual_http_stream_preserves_frame_bytes(mounted):
    with mounted.stream('GET', '/__transport_probe?stream=1') as response:
        assert response.status_code == 200
        assert response.headers['content-type'].startswith('text/event-stream')
        assert b''.join(response.iter_bytes()) == b'id: 1\nevent: probe\ndata: {"transport":true}\n\n'
