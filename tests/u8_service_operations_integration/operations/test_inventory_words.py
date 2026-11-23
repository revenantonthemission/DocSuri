"""The operator tool's inventory words and the Cloudflare export reader (U8 plan Step 32;
the person's decisions of 2026-10-24, "Add operator commands" and "Cloudflare's
numbers"; BR9.11, BR9.14, Workflow 11).

v1 keeps no access records on this Mac: the consumer inventory comes from a request-
analytics export you take from Cloudflare's dashboard. The reader keeps counts only and
drops every other field unread; it refuses an oversized or unknown file; v1's peak rate
is the busiest interval's requests over its length; and the install's `performance`
phase reads that rate through the install wiring.
"""

from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.u8_policy import SYNTHETIC_OPERATIONS
from docsuri_ops.migration import cloudflare_export, words
from docsuri_ops.migration.inventory import ConsumerInventory, client_ref
from docsuri_ops.u8_platform.decisions import Decisions
from docsuri_ops.u8_platform.u8_protocols import realm_operator
from tests.u8_service_operations_integration import platform_flows as pf
from tests.u8_service_operations_integration import recovery_flows as rf

BROWSER = "Mozilla/5.0 (Macintosh) Synthetic/1.0"
SCRIPT = "python-httpx/0.28"
PERSONAL = ("198.51.100.7", "KR", "8d1f2c3b4a5e6f70-ICN", "secret-value", "private")


def graphql(items: list[dict], group: str = "httpRequests1hGroups") -> bytes:
    return json.dumps({"data": {"viewer": {"zones": [{group: items}]}}, "errors": None}).encode()


def hour(at: str, requests: int, path: str | None = None, agent: str | None = None) -> dict:
    dimensions = {"datetime": at, "clientIP": "198.51.100.7", "clientCountryName": "KR",
                  "rayName": "8d1f2c3b4a5e6f70-ICN"}
    if path is not None:
        dimensions["clientRequestPath"] = path
    if agent is not None:
        dimensions["userAgent"] = agent
    return {"dimensions": dimensions, "sum": {"requests": requests}}


CSV = ("datetimeHour,requests,clientRequestPath,userAgent,clientIP,clientCountryName\n"
       "2026-10-20T09:00:00Z,30,/api/papers/2101.00001v2?token=secret-value,"
       f"{BROWSER},198.51.100.7,KR\n"
       f"2026-10-20T10:00:00Z,7,/api/search?q=private,{SCRIPT},198.51.100.7,KR\n").encode()


def private_file(path: Path, raw: bytes) -> Path:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
    return path


class Stage:
    def __init__(self, tmp_path, realm, clock):
        self.journey = pf.journey(tmp_path, realm)
        self.ledger = rf.open_ledger(tmp_path, clock)
        self.evidence = tmp_path / "evidence" / "inventory"
        operator = realm_operator(self.journey.profile, "operator", self.ledger, clock=clock)
        self.inventory = ConsumerInventory(
            self.ledger, window_seconds=SYNTHETIC_OPERATIONS.consumer_window_seconds,
            clock=clock, evidence=self.evidence)
        self.words = words.InventoryWords(self.inventory, words.InPerson(Decisions(
            operator, words.realm_appender(self.ledger, clock), clock=clock)))
        self.tmp = tmp_path

    def take(self, raw: bytes, document: dict | None = None) -> dict:
        path = private_file(self.tmp / f"export-{os.urandom(4).hex()}.csv", raw)
        return self.words.run("take", document or {}, export=path)


@pytest.fixture
def stage(tmp_path, realm, clock):
    value = Stage(tmp_path, realm, clock)
    yield value
    value.ledger.close()


# --- 3. counts only; an oversized or unknown file is refused ----------------------------------


@pytest.mark.parametrize("raw", [CSV, graphql([
    hour("2026-10-20T09:00:00Z", 30, "/api/papers/2101.00001v2?token=secret-value", BROWSER),
    hour("2026-10-20T10:00:00Z", 7, "/api/search?q=private", SCRIPT)])])
def test_the_reader_keeps_counts_only_and_drops_every_personal_field(stage, raw):
    taken = stage.take(raw)
    record = stage.ledger.get("consumer-inventory", taken["inventoryId"])
    evidence = (stage.evidence / f"consumer-inventory-{taken['inventoryId']}.json").read_text()
    for text in (json.dumps(record), evidence):
        for forbidden in (*PERSONAL, BROWSER, SCRIPT, "2101.00001"):
            assert forbidden not in text, forbidden
    assert [item["clientRef"] for item in record["consumers"]] == [
        client_ref(BROWSER), client_ref(SCRIPT)]
    assert {item["clientRef"]: item["routesUsed"] for item in record["consumers"]} == {
        client_ref(BROWSER): ["/api/papers/{id}"], client_ref(SCRIPT): ["/api/search"]}
    assert (record["requests"], record["intervalSeconds"]) == (37, 3600)
    # Each client's user agent is shown to you once, in the word's answer.
    assert {item["userAgent"] for item in taken["consumers"]} == {BROWSER, SCRIPT}


@pytest.mark.parametrize(("raw", "reason"), [
    (b"x" * (cloudflare_export.MAX_BYTES + 1), "export-too-large"),
    (b"time,visitors\n2026-10-20T09:00:00Z,3\n", "export-shape-unknown"),
    (json.dumps({"data": {"viewer": {"zones": [{"firewallEvents": []}]}}}).encode(),
     "export-shape-unknown"),
    (json.dumps({"data": None, "errors": [{"message": "not authorized"}]}).encode(),
     "export-carries-errors"),
    (b"datetime,requests\n", "export-empty"),
    (b"datetime,requests\nyesterday,4\n", "export-time-unreadable"),
    (b"datetime,requests\n2026-10-20T09:00:00Z,-4\n", "export-count-unreadable"),
    (b"datetime,requests\n2026-10-20T09:00:00Z,4\n", "export-interval-unknown"),
    (b"\xff\xfe not text", "export-shape-unknown"),
])
def test_an_oversized_or_unknown_export_is_refused(stage, raw, reason):
    with pytest.raises(words.Refused) as refused:
        stage.take(raw)
    assert (refused.value.code, refused.value.reason) == ("INVALID_INPUT", reason)
    assert stage.ledger.records("consumer-inventory") == []


def test_a_link_or_a_missing_export_is_refused(stage, tmp_path):
    target = private_file(tmp_path / "real.csv", CSV)
    link = tmp_path / "link.csv"
    link.symlink_to(target)
    with pytest.raises(words.Refused) as linked:
        stage.words.run("take", {}, export=link)
    assert linked.value.reason == "export-unreadable"
    with pytest.raises(words.Refused) as missing:
        stage.words.run("take", {})
    assert missing.value.reason == "cloudflare-export-required"


# --- 4. the peak rate comes from the busiest interval -------------------------------------------


def test_the_peak_is_the_busiest_interval_and_its_rate_its_requests_over_its_length(stage):
    taken = stage.take(graphql([
        hour("2026-10-20T09:00:00Z", 900), hour("2026-10-20T10:00:00Z", 120, "/a", BROWSER),
        hour("2026-10-20T10:00:00Z", 3480, "/b", SCRIPT), hour("2026-10-20T11:00:00Z", 3600),
    ]))
    # 10:00 holds 120 + 3480 = 3600, as 11:00 does: the earliest busiest interval.
    assert (taken["peakRequests"], taken["peakAt"]) == (3600, "2026-10-20T10:00:00.000Z")
    assert taken["peakRequestsPerSecond"] == 1.0
    assert (taken["observedFrom"], taken["observedUntil"]) == (
        "2026-10-20T09:00:00.000Z", "2026-10-20T12:00:00.000Z")


def test_a_plain_time_column_takes_its_smallest_gap_as_the_interval():
    export = cloudflare_export.read(b"timestamp,requests\n2026-10-20T09:00:00Z,6\n"
                                    b"2026-10-20T09:15:00Z,90\n2026-10-20T10:00:00Z,3\n")
    assert export.interval_seconds == 900 and export.peak_rate == 0.1
    daily = cloudflare_export.read(b"date,requests\n2026-10-20,86400\n")
    assert daily.interval_seconds == 86400 and daily.peak_rate == 1.0


# --- 5. the install's performance reads that rate ----------------------------------------------


def test_the_installs_performance_reads_the_inventorys_peak_rate(stage):
    from docsuri_ops.production_wiring import V1_INVENTORY_ENV, v1_inventory
    from scripts import verify_docsuri_u8

    scripts = str(Path(verify_docsuri_u8.ROOT) / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import u8_phases

    stage.take(graphql([hour("2026-10-20T09:00:00Z", 18_000, "/", BROWSER),
                        hour("2026-10-20T10:00:00Z", 3600, "/", BROWSER)]))
    handed = {V1_INVENTORY_ENV: json.dumps(v1_inventory(stage.ledger))}
    v1 = u8_phases.v1_request_rate(install=True, environ=handed)
    assert v1["requestsPerSecond"] == 5.0
    assert v1["source"]["peakAt"] == "2026-10-20T09:00:00.000Z"
    assert u8_phases.rate_check(3.69, v1) == "v1-rate-higher"
    assert u8_phases.rate_check(6.0, v1) is None


# --- dispositions, in two calls ----------------------------------------------------------------


def test_a_disposition_is_shown_then_recorded_and_completes_the_inventory(stage):
    taken = stage.take(CSV)
    consumer = {"inventoryId": taken["inventoryId"], "clientRef": client_ref(BROWSER),
                "disposition": "moves-with-v2"}
    shown = stage.words.run("record", consumer)
    assert shown["state"] == "shown" and shown["subject"]["routesUsed"] == ["/api/papers/{id}"]
    recorded = stage.words.run("record", {**consumer, "confirm": shown["digest"]})
    assert recorded == {"state": "recorded", "inventoryId": taken["inventoryId"],
                        "clientRef": client_ref(BROWSER), "disposition": "moves-with-v2",
                        "complete": False}
    other = {**consumer, "clientRef": client_ref(SCRIPT), "disposition": "accepted-to-break"}
    done = stage.words.run("record", {**other, "confirm": stage.words.run(
        "record", other)["digest"]})
    assert done["complete"] is True


def test_a_disposition_for_an_unknown_consumer_or_outside_its_set_is_refused(stage):
    taken = stage.take(CSV)
    with pytest.raises(words.Refused) as unknown:
        stage.words.run("record", {"inventoryId": taken["inventoryId"], "clientRef": "ua:0",
                                   "disposition": "informed"})
    assert unknown.value.code == "NOT_FOUND"
    with pytest.raises(words.Refused) as outside:
        stage.words.run("record", {"inventoryId": taken["inventoryId"],
                                   "clientRef": client_ref(BROWSER), "disposition": "kept"})
    assert outside.value.reason == "disposition-outside-its-set"


def test_the_inventory_words_refuse_production_without_the_installed_operator(monkeypatch):
    """The release names the account it authenticated (Step 119(d), D4): a stand-in
    keychain for the release answers a password generated per run (L1-36) and an account
    other than the installed operator, so nothing reaches this Mac's sudo or ledger."""
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(b"{}")))
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr("docsuri_ops.production_wiring._authorities",
                        lambda paths: {"actors": {"operator": "someone-else"}})
    released = bytearray(os.urandom(32).hex().encode())
    asked = []

    def release_with_actor(login):
        asked.append(login)
        return released, "another-account"

    monkeypatch.setattr("docsuri_ops.u8_platform.credential_release.release_with_actor",
                        release_with_actor)
    status = words.main("inventory", ["record", "--production"])
    assert status == 1 and json.loads(out.getvalue()) == {
        "ok": False, "code": "POLICY_UNRESOLVED", "reasonKey": "not-the-installed-operator"}
    assert asked == ["platform"] and set(released) == {0}


def test_the_inventory_words_answer_a_refused_release(monkeypatch):
    """A release that refuses (sudo's password refused, or no result naming the login) is
    one JSON refusal, never a traceback (the maintainer's decision of 2026-11-16)."""
    from docsuri_ops.u8_platform.credential_release import ReleaseRefused

    out = io.StringIO()
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(b"{}")))
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr("docsuri_ops.production_wiring._authorities",
                        lambda paths: {"actors": {"operator": "someone-else"}})
    asked = []

    def refused(login):
        asked.append(login)
        raise ReleaseRefused("the credential was not released")

    monkeypatch.setattr("docsuri_ops.u8_platform.credential_release.release_with_actor",
                        refused)
    status = words.main("inventory", ["record", "--production"])
    assert status == 1 and json.loads(out.getvalue()) == {
        "ok": False, "code": "POLICY_UNRESOLVED", "reasonKey": "credential-not-released"}
    assert asked == ["platform"]
