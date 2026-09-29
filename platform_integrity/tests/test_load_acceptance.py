"""The load harness must measure successful work and stay inside its isolated target."""

import io
import json
import runpy
import ssl
import urllib.error
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "ops/platform-integrity/load_acceptance.py"


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:18101", "https://127.0.0.1:8101",
    "https://user:password@127.0.0.1:18101", "https://127.0.0.1:18101/other",
    "https://127.0.0.1:18101?override=1", "https://127.0.0.1:18101#fragment",
])
def test_only_exact_isolated_origin_is_accepted(url):
    measure = runpy.run_path(str(SCRIPT))["measure"]
    with pytest.raises(ValueError):
        measure(url, "fixture", ssl.create_default_context(), seconds=1, rps=1)


def test_redirects_are_never_followed_with_client_credentials():
    handler = runpy.run_path(str(SCRIPT))["NoRedirect"]()
    with pytest.raises(urllib.error.HTTPError):
        handler.redirect_request(None, None, 302, "Moved", {}, "https://outside.test/")


def test_incomplete_or_denied_evidence_does_not_count_as_success(monkeypatch):
    module = runpy.run_path(str(SCRIPT))

    class Response(io.BytesIO):
        status = 200

    class Opener:
        def open(self, url, timeout):
            payload = {"alive": True} if url.endswith("healthz") else {"verdict": "INCOMPLETE"}
            return Response(json.dumps(payload).encode())

    monkeypatch.setattr(module["urllib"].request, "build_opener", lambda *args: Opener())
    result = module["measure"]("https://127.0.0.1:18101", "fixture", None, seconds=1, rps=5)
    assert result["state"] == "BLOCKED" and result["successes"] == 1
    assert len(result["failures"]) == 4 and not result["profileComplete"]
