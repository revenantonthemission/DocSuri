"""The complete host's static routes (U8 plan Step 40; A8, BR5.6, D3, P6).

`/privacy` and `/terms` are served signed out as script-free documents from the build,
`no-store`, whatever any capability's state; `/sign-in/callback/{provider}` is the
workspace shell for the two providers only; a missing document says the build is
missing; only content-hashed files may be cached.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from backend.modules.operations.readiness import CapabilityState
from tests.u8_service_operations_integration.host_flows import complete_host, fresh_client

LEGAL = "<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\"><title>{}</title>" \
        "</head><body><main><h1>{}</h1><p><a href=\"/search\">검색</a></p></main></body></html>"
SHELL = "<!doctype html><html lang=\"ko\"><body><div id=\"root\"></div>" \
        "<script type=\"module\" src=\"/assets/app-1a2b3c4d.js\"></script></body></html>"


def fixture_build(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "privacy.html").write_text(LEGAL.format("개인정보 처리방침", "개인정보 처리방침"))
    (folder / "terms.html").write_text(LEGAL.format("이용약관", "이용약관"))
    (folder / "index.html").write_text(SHELL)
    files = [{"path": name, "sha256": hashlib.sha256((folder / name).read_bytes()).hexdigest(),
              "size": (folder / name).stat().st_size, "contentHashed": False}
             for name in ("privacy.html", "terms.html", "index.html")]
    (folder / ".docsuri-build.json").write_text(json.dumps({"version": 1, "files": files}))
    return folder


@pytest.fixture
def host(realm, tmp_path, monkeypatch):
    import backend.u8_host as u8_host

    monkeypatch.setattr(u8_host, "BUILD", fixture_build(tmp_path / "dist"))
    with complete_host(realm) as value:
        yield value


def unavailable_everywhere(host) -> None:
    real = host.composition.readiness_view

    def view():
        readiness = real()
        states = {name: CapabilityState(name, "unavailable", "forced")
                  for name in readiness.contribution_of}
        readiness.states = lambda: states
        return readiness

    host.composition.readiness_view = view


@pytest.mark.parametrize("path,title", [("/privacy", "개인정보 처리방침"), ("/terms", "이용약관")])
def test_the_legal_documents_are_served_signed_out_without_scripts(host, path, title):
    unavailable_everywhere(host)
    answer = host.client.get(path)
    assert answer.status_code == 200, answer.text
    assert answer.headers["content-type"].startswith("text/html")
    assert answer.headers["cache-control"] == "no-store"
    assert "<script" not in answer.text.lower() and f"<h1>{title}</h1>" in answer.text
    assert 'lang="ko"' in answer.text


def test_the_callback_page_is_the_shell_for_each_provider_only(host):
    with fresh_client(host) as browser:
        assert not browser.cookies
        for provider in ("google", "orcid"):
            for query in ("flow=x&state=y&code=z", "error=access_denied&state=s"):
                answer = browser.get(f"/sign-in/callback/{provider}?{query}")
                assert answer.status_code == 200, (provider, query)
                assert answer.text == SHELL, (provider, query)
                assert answer.headers.get_list("cache-control") == ["no-store"]
                assert "set-cookie" not in answer.headers, (provider, query)
        assert browser.get("/sign-in/callback/github").status_code == 404


REPOSITORY_INDEX = Path(__file__).resolve().parents[3] / "frontend/dist/index.html"
# Security-design section 4's headers, written out as literals (Step 84(f)).
LITERAL_HEADERS = {
    "content-security-policy": (
        "default-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; "
        "frame-ancestors 'none'; form-action 'self' https://accounts.google.com "
        "https://orcid.org"
    ),
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
    "cross-origin-opener-policy": "same-origin",
}


def assert_fallback(answer) -> None:
    """The shared host's fallback over the repository's `frontend/dist`."""
    if answer.status_code == 503:
        assert answer.json()["messageKey"] == "build.missing"
        return
    assert answer.status_code == 200, answer.text
    assert answer.content == REPOSITORY_INDEX.read_bytes()


def test_the_shell_and_the_legal_pages_are_never_stored(host):
    callback = host.client.get("/sign-in/callback/google")
    assert callback.status_code == 200 and callback.text == SHELL
    legal = [host.client.get("/privacy"), host.client.get("/terms")]
    assert [answer.status_code for answer in legal] == [200, 200]
    fallbacks = [host.client.get("/"), host.client.get("/search")]
    for answer in fallbacks:
        assert_fallback(answer)
    for answer in (callback, *legal, *fallbacks):
        assert answer.headers.get_list("cache-control") == ["no-store"]


def test_the_html_answers_carry_the_literal_headers(host):
    answers = {
        "callback": host.client.get("/sign-in/callback/google"),
        "privacy": host.client.get("/privacy"),
        "terms": host.client.get("/terms"),
        "root": host.client.get("/"),
        "cross-site": host.client.get("/", headers={"origin": "https://elsewhere.example"}),
    }
    assert answers["callback"].status_code == 200
    assert answers["privacy"].status_code == 200 and answers["terms"].status_code == 200
    assert_fallback(answers["root"])
    refused = answers["cross-site"]
    assert refused.status_code == 403 and refused.json()["messageKey"] == "request.origin"
    for name, answer in answers.items():
        for header, value in LITERAL_HEADERS.items():
            assert answer.headers.get_list(header) == [value], (name, header)
        assert answer.headers.get_list("strict-transport-security") == [
            "max-age=31536000"
        ], name


def test_only_content_hashed_files_are_cacheable_and_a_missing_document_says_so(
    host, tmp_path,
):
    for path in ("/privacy", "/terms", "/sign-in/callback/google"):
        assert "immutable" not in host.client.get(path).headers["cache-control"]
    # The build is read at each request: a document that went missing says so.
    (tmp_path / "dist" / "terms.html").unlink()
    missing = host.client.get("/terms")
    assert (missing.status_code, missing.json()["messageKey"]) == (503, "build.missing")
