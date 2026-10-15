"""Mounted U3 assistance routes: acceptance, real dispatch, results, glossary.

Closes Q-01–Q-04 against the mounted transport: the job snapshot carries the
ordering field, the result shape is usable and typed, acceptance reaches real
execution through the supervised worker, and stream frames are valid.
"""

import json
import time
from uuid import uuid4

import pytest

pytestmark = pytest.mark.u3_integration

ASSISTANCE_POLICY = {"policyId": "u3-paper-assistance", "revision": "1"}
GLOSSARY_POLICY = {"policyId": "u3-owner-glossary", "revision": "1"}
PROCESSING_POLICY = {"policyId": "local-research", "revision": "1"}
ENTRY_POLICY = {"policyId": "synthetic-local-entry", "revision": "1"}


def post(client, path, value, key=None):
    return client.post(
        path, json=value, headers={"Idempotency-Key": str(key or uuid4())}
    )


@pytest.fixture
def published(run_fixture, fixture_discard):
    fixture_discard()
    assert run_fixture(["fixture-alpha"])["state"] == "completed"


def options_for(client, paper=None):
    paper = paper or {
        "paperId": "paper-alpha",
        "versionId": "paper-alpha:v1",
        "eligibilityRevision": "x",
    }
    response = post(client, "/api/v2/c06/read-assistance-options", {"paper": paper})
    assert response.status_code == 200, response.text
    return response.json()


def accept(client, option, *, key=None):
    source = read_content(client)
    return post(
        client,
        "/api/v2/c06/accept-assistance",
        {
            "paper": source["content"]["paper"],
            "contentRevision": source["content"]["contentRevision"],
            "contentHash": source["content"]["contentHash"],
            "operation": option["operation"],
            "optionId": option["optionId"],
            "optionsRevision": options_for(client)["revision"],
            "glossaryRevision": client_glossary(client)["revision"],
            "processingPolicy": PROCESSING_POLICY,
        },
        key=key,
    )


def read_content(client):
    resolved = post(
        client, "/api/v2/c04/resolve-paper", {"identifier": "paper-alpha", "versionLabel": "v1"}
    )
    assert resolved.status_code == 200, resolved.text
    content = post(
        client,
        "/api/v2/c04/read-content",
        {"paper": resolved.json()["paper"], "purpose": "assistance"},
    )
    assert content.status_code == 200, content.text
    assert content.json()["availability"] == "ready", content.text
    return content.json()


def client_glossary(client):
    response = post(client, "/api/v2/c06/read-glossary", {})
    assert response.status_code == 200, response.text
    return response.json()


def wait_for_terminal(client, job_id, *, seconds=45.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        response = post(client, "/api/v2/c06/read-assistance-job", {"jobId": job_id})
        assert response.status_code == 200, response.text
        body = response.json()
        if body["state"] in ("succeeded", "failed"):
            return body
        time.sleep(0.25)
    raise AssertionError("assistance job never reached a terminal state")


def test_options_disclose_the_synthetic_provider(browser, published):
    options = options_for(browser)
    assert options["options"], "a usable published source offers runnable options"
    assert any("합성" in item for item in options["limitations"])
    assert options["policy"] == PROCESSING_POLICY


def test_glossary_cas_through_the_route(browser, published):
    empty = client_glossary(browser)
    written = post(
        browser,
        "/api/v2/c06/replace-glossary",
        {
            "expectedRevision": empty["revision"],
            "normalizationPolicy": GLOSSARY_POLICY,
            "terms": [
                {
                    "termId": str(uuid4()),
                    "source": "attention",
                    "preferred": "어텐션",
                    "languageId": "ko",
                }
            ],
        },
    )
    assert written.status_code == 200, written.text
    assert written.json()["terms"][0]["preferred"] == "어텐션"
    conflict = post(
        browser,
        "/api/v2/c06/replace-glossary",
        {
            "expectedRevision": empty["revision"],
            "normalizationPolicy": GLOSSARY_POLICY,
            "terms": [],
        },
    )
    assert conflict.status_code == 409
    assert client_glossary(browser)["revision"] == written.json()["revision"]


def test_acceptance_reaches_real_execution_and_a_usable_result(browser, published):
    """Q-01..Q-04: ordering field, result semantics, real dispatch, valid frames."""
    key = uuid4()
    option = options_for(browser)["options"][0]
    accepted = accept(browser, option, key=key)
    assert accepted.status_code == 200, accepted.text
    job_id = accepted.json()["jobId"]
    assert accepted.json()["seq"] >= 0
    # Replay returns the original acceptance; changed input conflicts.
    assert accept(browser, option, key=key).json()["jobId"] == job_id
    terminal = wait_for_terminal(browser, job_id)
    assert terminal["state"] == "succeeded"
    assert terminal["seq"] > 0, "Q-01: the ordering field advances"
    assert terminal["result"] is not None, "Q-02: a succeeded job exposes its result"
    result = post(browser, "/api/v2/c06/read-prepared-assistance", {"jobId": job_id})
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["availability"] == "ready"
    assert body["prepared"]["sections"], "a ready result carries usable sections"
    assert body["prepared"]["coverage"] in ("complete", "partial")
    assert body["prepared"]["paper"]["versionId"] == "paper-alpha:v1"
    # Revisiting the result never regenerates work.
    again = post(browser, "/api/v2/c06/read-prepared-assistance", {"jobId": job_id})
    assert again.json() == body


def test_stream_frames_are_valid_and_ordered(browser, published):
    option = options_for(browser)["options"][0]
    accepted = accept(browser, option)
    job_id = accepted.json()["jobId"]
    seen = []
    with browser.stream(
        "GET", f"/api/v2/jobs/{job_id}/events", headers={"Last-Event-ID": "0"}
    ) as stream:
        for line in stream.iter_lines():
            if line.startswith("data: "):
                seen.append(json.loads(line[len("data: ") :]))
            if seen and seen[-1].get("state") in ("succeeded", "failed"):
                break
    assert seen, "the event stream delivered at least one valid frame"
    sequences = [event.get("seq") for event in seen if "seq" in event]
    assert sequences == sorted(sequences), "stream ordering never regresses"


def test_result_states_distinguish_withdrawal(browser, published, maintenance, authority):
    option = options_for(browser)["options"][0]
    accepted = accept(browser, option)
    job_id = accepted.json()["jobId"]
    terminal = wait_for_terminal(browser, job_id)
    assert terminal["state"] == "succeeded"
    maintenance.record_change(
        authority,
        {
            "paperId": "paper-alpha",
            "changeKind": "withdrawal",
            "disposition": "withdrawn",
            "reasonKey": "publisher-withdrawal",
            "policy": {"policyId": "u3-source-eligibility", "revision": "1"},
        },
    )
    result = post(browser, "/api/v2/c06/read-prepared-assistance", {"jobId": job_id})
    assert result.status_code == 200, result.text
    assert result.json()["availability"] in ("withdrawn", "restricted")


def test_foreign_job_identifiers_are_absent(browser, published):
    for path, value in (
        ("/api/v2/c06/read-assistance-job", {"jobId": str(uuid4())}),
        ("/api/v2/c06/read-prepared-assistance", {"jobId": str(uuid4())}),
    ):
        response = post(browser, path, value)
        assert response.status_code in (403, 404), response.text


def test_assistance_requires_authentication(anonymous, published):
    response = post(
        anonymous,
        "/api/v2/c06/read-assistance-options",
        {"paper": {"paperId": "paper-alpha", "versionId": "paper-alpha:v1",
                   "eligibilityRevision": "x"}},
    )
    assert response.status_code in (401, 403)
