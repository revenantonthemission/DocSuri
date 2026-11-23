"""A paper's assets through the complete host (U8 plan Steps 84(g), 128; D7, SECURITY-08,
SEC-9, record 60, L2-9).

`POST /api/v2/c04/read-asset` resolves an opaque asset handle under the reader's current
authority and the version's current eligibility and answers a read handle, the asset's id.
C13's byte route, `GET /api/v2/papers/{paper_id}/versions/{version_id}/assets/{asset_id}`,
delivers that asset's bytes from the host's own origin under `Cache-Control: no-store` and
`X-Content-Type-Options: nosniff`, with the session and the version's eligibility checked
again on every delivery. No answer names a presigned address. The bytes these tests deliver
are their own, published to the composition's corpus store; the reading surface still shows
each figure's caption only, so no product code calls either route (L2-9).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from psycopg.types.json import Jsonb

from backend.local_browser import SESSION_COOKIE
from backend.log_events import EVENTS_LOGGER
from backend.modules.corpus.repository import content_revision
from tests.u8_service_operations_integration.conftest import ORIGIN, post
from tests.u8_service_operations_integration.host_flows import (
    call,
    complete_host,
    csrf,
    fresh_client,
    member,
)

ROOT = Path(__file__).resolve().parents[3]
PATH = "/api/v2/c04/read-asset"
PRESIGNED_MARKERS = ("://", "X-Amz-", "Signature=", "Expires=")
REFUSAL_FIELDS = {"code", "requestId", "retryable", "messageKey"}
# C13's byte route, written out so the test pins the contract's path.
BYTE_ROUTE = "/api/v2/papers/{paper_id}/versions/{version_id}/assets/{asset_id}"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def byte_path(paper_id: str, version_id: str, asset_id: str) -> str:
    return BYTE_ROUTE.format(paper_id=paper_id, version_id=version_id, asset_id=asset_id)


@pytest.fixture
def host(realm, own_address):
    with complete_host(realm, address=own_address) as value:
        yield value


def section_content(label: str) -> dict:
    return {"document": {"sections": [{"id": "s1", "title": "Body", "blocks": [
        {"id": "s1.p1", "type": "paragraph", "text": f"Synthetic asset paper {label}."},
    ]}]}}


@pytest.fixture
def paper(connect):
    """Two eligible `local-research` versions of a paper of the test's own, each with one
    `corpus.asset` row, written through the corpus owner's login."""
    token = secrets.token_hex(4)
    paper_id = f"u8pa-{token}"
    versions = []
    with connect("corpus") as conn:
        conn.execute("INSERT INTO corpus.paper(id,title,authors,metadata) "
                     "VALUES(%s,'Synthetic asset paper','[]','{}')", (paper_id,))
        for label in ("v1", "v2"):
            version_id, revision, content = f"{paper_id}-{label}", uuid4(), section_content(label)
            conn.execute(
                "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,"
                "private_path,eligible,purpose,eligibility_revision,provenance,content) VALUES"
                "(%s,%s,'https://fixture.example.com/paper',%s,%s,'fixture',true,"
                "'local-research',%s,'{}',%s)",
                (version_id, paper_id, secrets.token_hex(32), label, revision, Jsonb(content)))
            asset_id = uuid4()
            conn.execute(
                "INSERT INTO corpus.asset(id,version_id,section_id,media_type,content_hash,"
                "storage,byte_length,alt_text) VALUES(%s,%s,'s1','image/png',%s,'private',"
                "1024,'합성 그림')",
                (asset_id, version_id, hashlib.sha256(asset_id.bytes).hexdigest()))
            versions.append({
                "paper": {"paperId": paper_id, "versionId": version_id,
                          "eligibilityRevision": str(revision)},
                "contentRevision": content_revision({"content": content}),
                "assetId": str(asset_id),
            })
    return versions


@pytest.fixture
def stored(host, connect):
    """A paper of the test's own with two eligible `local-research` versions whose assets'
    bytes are published to the composition's own corpus store, generated per run (L1-36):
    on version 1 a PNG, an SVG holding a script and an `unavailable` row with no bytes; on
    version 2 a PNG. The fixture's artifacts are erased afterwards."""
    files = host.composition.parts["paper-corpus"]["files"]
    token = secrets.token_hex(4)
    paper_id = f"u8pb-{token}"
    published, versions, assets = [], [], {}

    def write_asset(conn, version_id: str, media_type: str, content: bytes | None) -> dict:
        if content is None:
            asset_id, digest, size, storage = uuid4(), secrets.token_hex(32), None, "unavailable"
        else:
            artifact = files.publish(content)
            published.append(artifact.name)
            asset_id = UUID(artifact.name.removesuffix(".blob"))
            digest, size, storage = artifact.sha256, artifact.size, "private"
        conn.execute(
            "INSERT INTO corpus.asset(id,version_id,section_id,media_type,content_hash,"
            "storage,byte_length,alt_text) VALUES(%s,%s,'s1',%s,%s,%s,%s,'합성 그림')",
            (asset_id, version_id, media_type, digest, storage, size))
        return {"id": str(asset_id), "versionId": version_id, "content": content,
                "name": asset_id.hex + ".blob"}

    svg = (b'<svg xmlns="http://www.w3.org/2000/svg"><!-- ' + secrets.token_hex(8).encode()
           + b' --><script>document.title="x"</script></svg>')
    try:
        with connect("corpus") as conn:
            conn.execute("INSERT INTO corpus.paper(id,title,authors,metadata) "
                         "VALUES(%s,'Synthetic asset bytes paper','[]','{}')", (paper_id,))
            for label in ("v1", "v2"):
                version_id, revision = f"{paper_id}-{label}", uuid4()
                content = section_content(label)
                conn.execute(
                    "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,"
                    "version_label,private_path,eligible,purpose,eligibility_revision,"
                    "provenance,content) VALUES(%s,%s,'https://fixture.example.com/paper',"
                    "%s,%s,'fixture',true,'local-research',%s,'{}',%s)",
                    (version_id, paper_id, secrets.token_hex(32), label, revision,
                     Jsonb(content)))
                versions.append({
                    "paper": {"paperId": paper_id, "versionId": version_id,
                              "eligibilityRevision": str(revision)},
                    "contentRevision": content_revision({"content": content}),
                })
            first, second = versions[0]["paper"]["versionId"], versions[1]["paper"]["versionId"]
            assets["png"] = write_asset(conn, first, "image/png",
                                        PNG_SIGNATURE + secrets.token_bytes(64))
            assets["svg"] = write_asset(conn, first, "image/svg+xml", svg)
            assets["unavailable"] = write_asset(conn, first, "image/png", None)
            assets["png2"] = write_asset(conn, second, "image/png",
                                         PNG_SIGNATURE + secrets.token_bytes(64))
        yield {"paperId": paper_id, "versions": versions, "assets": assets, "files": files}
    finally:
        for name in published:
            files.erase(name)


def bytes_of(client, paper_id: str, asset: dict, **headers):
    return client.get(byte_path(paper_id, asset["versionId"], asset["id"]), headers=headers)


def read_asset(client, version: dict, asset_id: str):
    return call(client, PATH, {"paper": version["paper"],
                               "contentRevision": version["contentRevision"],
                               "assetId": asset_id})


def refusal(answer, status: int, code: str) -> dict:
    assert (answer.status_code, answer.json()["code"]) == (status, code), answer.text
    body = answer.json()
    assert set(body) == REFUSAL_FIELDS, body
    return {key: value for key, value in body.items() if key != "requestId"}


def test_each_asset_delivery_checks_authority_again_and_names_no_presigned_address(
    host, sign_in_account, connect, paper,
):
    member(host, sign_in_account)
    first, second = paper

    delivered = read_asset(host.client, first, first["assetId"])
    assert delivered.status_code == 200, delivered.text
    assert delivered.json()["readHandle"] == first["assetId"]
    serialized = json.dumps(delivered.json())
    for marker in PRESIGNED_MARKERS:
        assert marker not in serialized, marker
    assert "location" not in delivered.headers
    assert not 300 <= delivered.status_code < 400
    assert delivered.headers.get_list("cache-control") == ["no-store"]

    # Another version's asset and an identifier no version has answer alike.
    other_version = read_asset(host.client, first, second["assetId"])
    unknown = read_asset(host.client, first, str(uuid4()))
    assert refusal(other_version, 404, "NOT_FOUND") == refusal(unknown, 404, "NOT_FOUND")

    # The version made ineligible through the corpus owner's login: refused at once.
    with connect("corpus") as conn:
        conn.execute("UPDATE corpus.version SET eligible=false, eligibility_revision=%s "
                     "WHERE id=%s", (uuid4(), first["paper"]["versionId"]))
    refusal(read_asset(host.client, first, first["assetId"]), 404, "NOT_FOUND")

    # A session revoked by sign-out, replayed with its CSRF token, is refused.
    session = host.client.cookies.get(SESSION_COOKIE)
    token = csrf(host.client)
    assert session
    assert call(host.client, "/api/v2/c02/access-logout", {}).status_code == 200
    body = {"paper": second["paper"], "contentRevision": second["contentRevision"],
            "assetId": second["assetId"]}
    with fresh_client(host) as replay:
        replayed = replay.post(PATH, json=body, headers={
            "origin": ORIGIN, "x-csrf-token": token, "idempotency-key": str(uuid4()),
            "cookie": f"{SESSION_COOKIE}={session}",
        })
        refusal(replayed, 404, "FORBIDDEN")
    with fresh_client(host) as signed_out:
        assert not signed_out.cookies
        refusal(post(signed_out, PATH, body, token), 401, "UNAUTHENTICATED")


# --- C13's byte route (Step 128; L2-9) ---------------------------------------------------


def test_a_papers_asset_bytes_are_delivered_from_the_same_origin(host, sign_in_account, stored):
    member(host, sign_in_account)
    paper_id, first = stored["paperId"], stored["versions"][0]
    png, svg = stored["assets"]["png"], stored["assets"]["svg"]

    handle = read_asset(host.client, first, png["id"])
    assert handle.status_code == 200, handle.text
    assert handle.json()["readHandle"] == png["id"]

    delivered = host.client.get(byte_path(paper_id, png["versionId"], handle.json()["readHandle"]))
    assert delivered.status_code == 200, delivered.text
    assert delivered.content == png["content"]
    assert delivered.headers["content-type"] == "image/png"
    assert delivered.headers.get_list("cache-control") == ["no-store"]
    assert delivered.headers["x-content-type-options"] == "nosniff"
    assert delivered.headers["content-length"] == str(len(png["content"]))
    assert "location" not in delivered.headers
    assert "content-disposition" not in delivered.headers
    assert not 300 <= delivered.status_code < 400

    # An unsafe type goes out as an attachment, never inline.
    attached = bytes_of(host.client, paper_id, svg)
    assert attached.status_code == 200, attached.text
    assert attached.content == svg["content"]
    assert attached.headers["content-type"] == "application/octet-stream"
    assert attached.headers["content-disposition"] == "attachment"

    # A range request gets the whole body.
    ranged = bytes_of(host.client, paper_id, png, range="bytes=0-3")
    assert (ranged.status_code, ranged.content) == (200, png["content"])


def test_each_byte_delivery_checks_the_session_and_eligibility_again(
    host, sign_in_account, connect, stored,
):
    member(host, sign_in_account)
    paper_id, first = stored["paperId"], stored["versions"][0]["paper"]["versionId"]
    second = stored["versions"][1]["paper"]["versionId"]
    png2, svg = stored["assets"]["png2"], stored["assets"]["svg"]

    def get(paper: str, version: str, asset: str):
        return host.client.get(byte_path(paper, version, asset))

    # Another version's asset, an identifier no version has and a malformed one: alike.
    missing = [refusal(get(paper_id, first, asset), 404, "NOT_FOUND")
               for asset in (png2["id"], str(uuid4()), "not-a-uuid")]
    assert missing[0] == missing[1] == missing[2]

    # The version is checked before the asset id is parsed (U1's order).
    unknown_version = f"{paper_id}-v9"
    for paper, version, asset in ((f"u8pb-{secrets.token_hex(4)}", first, svg["id"]),
                                  (paper_id, unknown_version, svg["id"]),
                                  (paper_id, unknown_version, "not-a-uuid")):
        refusal(get(paper, version, asset), 404, "FORBIDDEN")

    # Identifiers outside C13's `Id` form are refused before any SQL.
    for paper, version, asset in ((paper_id, "v%00x", svg["id"]),
                                  (paper_id, "v" * 129, svg["id"]),
                                  (paper_id, first, "a%01b")):
        refusal(get(paper, version, asset), 404, "FORBIDDEN")

    # Eligibility is read on every delivery.
    assert get(paper_id, second, png2["id"]).status_code == 200
    with connect("corpus") as conn:
        conn.execute("UPDATE corpus.version SET eligible=false, eligibility_revision=%s "
                     "WHERE id=%s", (uuid4(), second))
    refusal(get(paper_id, second, png2["id"]), 404, "FORBIDDEN")

    # A session ended by sign-out, replayed, is refused.
    session = host.client.cookies.get(SESSION_COOKIE)
    assert session
    assert call(host.client, "/api/v2/c02/access-logout", {}).status_code == 200
    with fresh_client(host) as replay:
        replayed = replay.get(byte_path(paper_id, first, svg["id"]),
                              headers={"cookie": f"{SESSION_COOKIE}={session}"})
        refusal(replayed, 401, "UNAUTHENTICATED")

    # No session at all: refused before any identifier is read.
    with fresh_client(host) as signed_out:
        assert not signed_out.cookies
        anonymous = [
            refusal(signed_out.get(byte_path(paper_id, first, svg["id"])), 401,
                    "UNAUTHENTICATED"),
            refusal(signed_out.get(byte_path(f"u8pb-{secrets.token_hex(4)}", str(uuid4()),
                                             str(uuid4()))), 401, "UNAUTHENTICATED"),
        ]
    assert anonymous[0] == anonymous[1]


def asset_lines(caplog, asset_id: str) -> list[dict]:
    lines = []
    for record in caplog.records:
        if record.name != EVENTS_LOGGER:
            continue
        line = json.loads(record.getMessage())
        if line.get("event") == "asset.unavailable" and line.get("objectId") == asset_id:
            lines.append(line)
    return lines


def test_an_asset_without_intact_bytes_answers_not_found_and_is_logged(
    host, sign_in_account, stored, caplog,
):
    caplog.set_level(logging.DEBUG, logger=EVENTS_LOGGER)
    member(host, sign_in_account)
    paper_id, png = stored["paperId"], stored["assets"]["png"]
    unavailable = stored["assets"]["unavailable"]

    refusal(bytes_of(host.client, paper_id, unavailable), 404, "NOT_FOUND")
    assert asset_lines(caplog, unavailable["id"]) == []

    # Overwritten in place with as many other bytes: its owner and 0600 kept.
    path = stored["files"].root / png["name"]
    descriptor = os.open(path, os.O_WRONLY | os.O_NOFOLLOW)
    try:
        os.write(descriptor, secrets.token_bytes(len(png["content"])))
    finally:
        os.close(descriptor)
    refusal(bytes_of(host.client, paper_id, png), 404, "NOT_FOUND")
    lines = asset_lines(caplog, png["id"])
    assert [(line["component"], line["level"], line["reason"]) for line in lines] == [
        ("corpus", "warning", "artifact-unavailable")]

    # Removed: refused again, with a second line.
    path.unlink()
    refusal(bytes_of(host.client, paper_id, png), 404, "NOT_FOUND")
    assert len(asset_lines(caplog, png["id"])) == 2


CHILD = """
import json, os, sys
from pathlib import Path
from backend.local_profile import LocalProfile
from backend.u8_host import compose, host_app

profile = LocalProfile.load(Path(os.environ["DOCSURI_U8_ENVIRONMENT_FILE"]))
composition = compose(profile)
try:
    host_app(composition)
    summarization_src = str(Path(sys.argv[1]).resolve())
    loaded = sorted(
        name for name, module in list(sys.modules.items())
        if (getattr(module, "__file__", None) or "").startswith(summarization_src + os.sep)
    )
    print(json.dumps({"underSrc": loaded,
                      "topLevel": "summarization" in sys.modules}))
finally:
    composition.close()
"""


def test_the_complete_assembly_has_two_asset_routes_and_loads_no_presigning_code(host):
    assets = {key: value for key, value in host.app.state.route_inventory.items()
              if value[0] == "asset"}
    assert assets == {("POST", PATH): ("asset", "guarded"),
                      ("GET", BYTE_ROUTE): ("asset", "guarded")}

    source = ROOT / "backend/modules/summarization/src"
    environment = {**os.environ, "PYTHONPATH": str(ROOT),
                   "DOCSURI_U8_ENVIRONMENT_FILE": os.environ["DOCSURI_U8_ENVIRONMENT_FILE"]}
    child = subprocess.run([sys.executable, "-c", CHILD, str(source)], cwd=ROOT,
                           env=environment, capture_output=True, timeout=120, check=False)
    assert child.returncode == 0, child.stderr.decode()[-2000:]
    loaded = json.loads(child.stdout.decode().strip().splitlines()[-1])
    assert loaded == {"underSrc": [], "topLevel": False}


# --- the isolation journeys' own paper (L3-5) --------------------------------------------


def fixture_assets_module():
    from scripts import verify_docsuri_u8

    folder = str(Path(verify_docsuri_u8.ROOT) / "scripts")
    if folder not in sys.path:
        sys.path.insert(0, folder)
    import u8_fixture_assets

    return u8_fixture_assets


def test_the_isolation_fixtures_paper_asset_reads_through_both_routes(host, sign_in_account):
    """L3-5: the paper `fixtures` records for J03 and J13 reads as the browser test
    expects: the eligible version's asset through both routes with its exact bytes, the
    ineligible one refused on each; a second call with the record returns it unchanged
    and publishes nothing."""
    assets = fixture_assets_module()
    files = host.composition.parts["paper-corpus"]["files"]
    transactions = host.composition.transactions
    published_before = {path.name for path in files.root.iterdir()}
    record = assets.paper_asset(transactions, files, None)
    try:
        member(host, sign_in_account)
        eligible, ineligible = record["eligible"], record["ineligible"]
        paper_id = record["paperId"]
        handle = read_asset(host.client, eligible, eligible["assetId"])
        assert handle.status_code == 200, handle.text
        assert handle.json()["readHandle"] == eligible["assetId"]
        delivered = host.client.get(byte_path(paper_id, eligible["paper"]["versionId"],
                                              eligible["assetId"]))
        assert delivered.status_code == 200, delivered.text
        assert hashlib.sha256(delivered.content).hexdigest() == eligible["sha256"]
        assert delivered.content.startswith(PNG_SIGNATURE)
        refusal(read_asset(host.client, ineligible, ineligible["assetId"]), 404, "NOT_FOUND")
        refusal(host.client.get(byte_path(paper_id, ineligible["paper"]["versionId"],
                                          ineligible["assetId"])), 404, "FORBIDDEN")
        published = {path.name for path in files.root.iterdir()}
        assert assets.paper_asset(transactions, files, record) == record
        assert {path.name for path in files.root.iterdir()} == published
        assert len(published - published_before) == 2
    finally:
        for kind in ("eligible", "ineligible"):
            files.erase(UUID(record[kind]["assetId"]).hex + ".blob")


def test_the_fixtures_assistance_job_is_ready_and_its_owner_reads_its_result(realm):
    """L4-13: the job `fixtures` makes for memberA's pass of the isolation journey is
    ready, and its owner reads the job, its result and its place in the history; another
    owner reads none of it; a second call with the record returns it unchanged.

    It runs on a production stand-in of its own, with owners of its own: PaperAssistance
    admits at most four open jobs in a database and two for an owner, and the realm's
    shared database holds whatever the phases before left open, so on the shared realm
    this test's admission depended on them. The routes the browser asks are asked of
    these records by the isolation journey itself."""
    from backend.artifacts import PrivateArtifacts
    from backend.modules.corpus.limits import for_profile
    from backend.modules.summarization.guarded_repository import GuardedAssistanceRepository
    from backend.modules.summarization.local_result import decode_result
    from tests.u8_service_operations_integration.host_flows import (
        production_stand_in,
        standin_account,
    )

    fixture_assets_module()
    import u8_fixture_assistance

    with production_stand_in(realm) as standin:
        owner = standin_account(standin, "assistance-fixture")
        other = standin_account(standin, "assistance-other", grant=False)
        transactions = standin.transactions
        files = PrivateArtifacts.for_profile(
            standin.profile, "corpus-files",
            maximum_bytes=for_profile(standin.profile).max_source_bytes)
        record = u8_fixture_assistance.assistance_job(transactions, files, owner, None)
        job_id = UUID(record["jobId"])
        repository = GuardedAssistanceRepository(transactions, files)

        job = repository.disposition_snapshot(owner, job_id)
        assert (job["state"], job["account_id"]) == ("succeeded", owner.account_id)
        assert job["version_id"] == record["paper"]["versionId"]
        reference = repository.result_reference(owner, job_id)
        assert reference is not None, "the fixture's job holds no result"
        assert (reference["resultId"], reference["revision"], reference["contentHash"]) == (
            record["resultId"], record["revision"], record["contentHash"])
        document = decode_result(repository.result(owner, UUID(reference["resultId"])))
        assert document["sections"], document
        assert job_id in {row["id"] for row in repository.history(owner, 20)}
        # Another owner of the same database reads none of it.
        assert repository.result_reference(other, job_id) is None
        with pytest.raises(PermissionError):
            repository.disposition_snapshot(other, job_id)
        assert job_id not in {row["id"] for row in repository.history(other, 20)}
        assert u8_fixture_assistance.assistance_job(
            transactions, files, owner, record) == record
