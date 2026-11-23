"""The consumer inventory (U8 plan Step 32; BR9.11, BR9.14, Workflow 11).

From your Cloudflare export (the person's decision of 2026-10-24, "Cloudflare's
numbers"), only the user agent and the route family of each row are kept, with request
counts; each consumer's disposition is recorded by your decision, and the inventory is
complete only when every consumer has one.
"""

from __future__ import annotations

import json

import pytest

from backend.modules.operations.errors import OperationsError
from docsuri_ops.migration import cloudflare_export
from docsuri_ops.migration.inventory import ConsumerInventory, client_ref, route_family
from tests.u8_service_operations_integration import recovery_flows as rf

WINDOW = 14 * 24 * 3600
BROWSER = "Mozilla/5.0 (Macintosh) Synthetic/1.0"
SCRIPT = "python-httpx/0.28"


@pytest.fixture
def ledger(tmp_path, clock):
    value = rf.open_ledger(tmp_path, clock)
    yield value
    value.close()


def export(rows: list[tuple[str, int, str, str]]):
    """A Cloudflare CSV export with an address column the reader must never keep."""
    lines = ["datetimeHour,requests,clientRequestPath,userAgent,clientIP"]
    lines += [f"{at},{count},{path},{agent},198.51.100.7" for at, count, path, agent in rows]
    return cloudflare_export.read("\n".join(lines).encode())


def observed_inventory(ledger, clock, tmp_path=None):
    inventory = ConsumerInventory(ledger, window_seconds=WINDOW, clock=clock,
                                  evidence=tmp_path)
    observed = inventory.observe(export([
        ("2026-10-20T09:00:00Z", 30, "/api/papers/2101.00001v2?token=secret-value", BROWSER),
        ("2026-10-20T09:00:00Z", 12,
         "/api/library/items/3f2a9c1e-0000-4000-8000-00000000abcd", BROWSER),
        ("2026-10-20T10:00:00Z", 7, "/api/search?q=private+query", SCRIPT),
    ]))
    return inventory, observed


def test_only_the_user_agent_and_the_route_family_are_kept(ledger, clock, tmp_path):
    inventory, observed = observed_inventory(ledger, clock, tmp_path)
    assert observed == [
        {"clientRef": client_ref(BROWSER), "userAgent": BROWSER,
         "routesUsed": ["/api/library/items", "/api/papers/{id}"], "requests": 42},
        {"clientRef": client_ref(SCRIPT), "userAgent": SCRIPT, "routesUsed": ["/api/search"],
         "requests": 7},
    ]
    record = inventory.record(observed, known=[{"clientRef": "integration:notion-import",
                                                "routesUsed": ["/api/export"]}])
    evidence = (tmp_path / f"consumer-inventory-{record['inventoryId']}.json").read_text()
    for text in (json.dumps(record), evidence):
        for forbidden in ("198.51.100.7", "secret-value", "private", "2101.00001", "3f2a9c1e",
                          BROWSER, SCRIPT):
            assert forbidden not in text, forbidden
    assert [item["source"] for item in record["consumers"]] == ["observed", "observed", "known"]
    assert record["complete"] is False
    # The export's window, request count and busiest interval: v1's peak rate.
    assert (record["observedFrom"], record["observedUntil"]) == (
        "2026-10-20T09:00:00.000Z", "2026-10-20T11:00:00.000Z")
    assert (record["requests"], record["peakRequests"], record["intervalSeconds"]) == (
        49, 42, 3600)
    assert record["peakAt"] == "2026-10-20T09:00:00.000Z"
    assert record["source"] == "cloudflare-export"
    counts = json.loads(evidence)
    assert counts["series"] == [{"at": "2026-10-20T09:00:00.000Z", "requests": 42},
                                {"at": "2026-10-20T10:00:00.000Z", "requests": 7}]
    assert counts["routes"] == {"/api/library/items": 12, "/api/papers/{id}": 30,
                                "/api/search": 7}


def test_an_inventory_recorded_without_an_export_has_no_counts(ledger, clock):
    inventory = ConsumerInventory(ledger, window_seconds=WINDOW, clock=clock)
    record = inventory.record([], known=[{"clientRef": "integration:notion-import",
                                          "routesUsed": ["/api/export"]}])
    assert not {"source", "requests", "peakRequests"} & set(record)


def test_route_families_replace_identifiers_and_drop_queries():
    assert route_family("/api/papers/2101.00001v3/assets/42") == "/api/papers/{id}"
    assert route_family("/API/Users/ABCDEF0123456789ABCDEF/profile") == "/api/users/{id}"
    assert route_family("/health?probe=1") == "/health"
    assert route_family("relative/path") is None
    assert route_family("/odd segment/x") == "/{id}/x"


def test_each_consumers_disposition_is_recorded_by_your_decision(ledger, clock):
    inventory, observed = observed_inventory(ledger, clock)
    record = inventory.record(observed)
    browser, script = client_ref(BROWSER), client_ref(SCRIPT)
    wrong = rf.approval_record(ledger, "consumer-disposition", script, now=clock())
    with pytest.raises(OperationsError) as refused:
        inventory.dispose(record["inventoryId"], browser, "moves-with-v2", wrong["approvalId"])
    assert refused.value.code == "FORBIDDEN"
    with pytest.raises(OperationsError):
        inventory.dispose(record["inventoryId"], browser, "kept-somehow", wrong["approvalId"])
    first = rf.approval_record(ledger, "consumer-disposition", browser, now=clock())
    partial = inventory.dispose(record["inventoryId"], browser, "moves-with-v2",
                                first["approvalId"])
    assert partial["complete"] is False
    done = inventory.dispose(record["inventoryId"], script, "accepted-to-break",
                             wrong["approvalId"])
    assert done["complete"] is True
    assert [(item["disposition"], item["approvalId"]) for item in done["consumers"]] == [
        ("moves-with-v2", first["approvalId"]), ("accepted-to-break", wrong["approvalId"])]
    declined = rf.approval_record(ledger, "consumer-disposition", browser, now=clock(),
                                  decision="declined")
    with pytest.raises(OperationsError):
        inventory.dispose(record["inventoryId"], browser, "informed", declined["approvalId"])


def test_an_empty_inventory_is_complete_and_an_unknown_one_is_not_found(ledger, clock):
    inventory = ConsumerInventory(ledger, window_seconds=WINDOW, clock=clock)
    assert inventory.record([])["complete"] is True
    from uuid import uuid4

    approval = rf.approval_record(ledger, "consumer-disposition", "ua:0", now=clock())
    with pytest.raises(OperationsError) as missing:
        inventory.dispose(uuid4(), "ua:0", "informed", approval["approvalId"])
    assert missing.value.code == "NOT_FOUND"
