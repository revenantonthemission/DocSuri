"""The restore-enforcement register (U8 plan Step 14; BR4.6, NFR4.3).

Every case uses a real ledger in a private temporary folder.
"""

from __future__ import annotations

import datetime as dt
import os
from uuid import uuid4

import pytest

from backend.modules.operations.errors import LedgerDamaged
from backend.modules.operations.ledger import Ledger, LedgerStore, canonical
from backend.modules.operations.tombstones import KIND, Tombstones, tombstone_digest


@pytest.fixture
def folder(tmp_path):
    path = tmp_path / "ledger"
    path.mkdir(mode=0o700)
    return path


def rewrite(path, payload: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_TRUNC)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)


def test_a_claim_appends_once_and_a_retried_claim_appends_nothing(folder, clock):
    ledger = Ledger.open(folder, clock=clock)
    try:
        register = Tombstones(ledger)
        account, request = uuid4(), uuid4()
        first = register.claim(account, request)
        head = ledger.head
        again = register.claim(account, request)
        assert again == first and ledger.head == head
        assert first["sequence"] == 1 and first["previousDigest"] == "0" * 64
        second = register.claim(uuid4(), uuid4())
        assert second["sequence"] == 2 and second["previousDigest"] == first["digest"]
        assert register.head() == {"sequence": 2, "digest": second["digest"]}
        assert register.verify() == register.head()
        with pytest.raises(LedgerDamaged):
            register.claim(uuid4(), request)  # the same request for another owner
        assert set(first) == {"sequence", "accountId", "lifecycleRequestId", "appendedAt",
                              "previousDigest", "digest"}
    finally:
        ledger.close()


def test_two_components_share_one_gap_free_sequence(folder, clock):
    first, second = Ledger.open(folder, clock=clock), Ledger.open(folder, clock=clock)
    try:
        a = Tombstones(first).claim(uuid4(), uuid4())
        b = Tombstones(second).claim(uuid4(), uuid4())
        assert (a["sequence"], b["sequence"]) == (1, 2)
        assert b["previousDigest"] == a["digest"]
    finally:
        first.close()
        second.close()


def test_truncation_is_detected_against_a_recorded_head(folder, clock):
    ledger = Ledger.open(folder, clock=clock)
    register = Tombstones(ledger)
    for _ in range(3):
        register.claim(uuid4(), uuid4())
    recorded = register.head()  # what an erase evidence recorded
    ledger.close()
    # The ledger cut back consistently to two entries, its head rewritten to match.
    log, head = folder / LedgerStore.LOG, folder / LedgerStore.HEAD
    lines = log.read_bytes().split(b"\n")
    kept = b"\n".join(lines[:2]) + b"\n"
    from backend.modules.operations.ledger import entry_digest

    rewrite(log, kept)
    rewrite(head, canonical({"count": 2, "head": entry_digest(lines[1])}))
    reopened = Ledger.open(folder, clock=clock)
    try:
        with pytest.raises(LedgerDamaged) as raised:
            Tombstones(reopened).verify(recorded)
        assert raised.value.category == "register-truncated"
    finally:
        reopened.close()
    # A cut without rewriting the head is caught by the file layer itself.
    rewrite(log, lines[0] + b"\n")
    with pytest.raises(LedgerDamaged):
        Ledger.open(folder, clock=clock)


def test_a_forged_tombstone_breaks_the_register(folder, clock):
    ledger = Ledger.open(folder, clock=clock)
    try:
        register = Tombstones(ledger)
        first = register.claim(uuid4(), uuid4())
        # A record written past the component with a digest that does not recompute.
        ledger.store.append_entry(KIND, {
            "sequence": 2, "accountId": str(uuid4()), "lifecycleRequestId": str(uuid4()),
            "appendedAt": first["appendedAt"], "previousDigest": first["digest"],
            "digest": "f" * 64,
        })
        with pytest.raises(LedgerDamaged) as raised:
            register.verify()
        assert raised.value.category == "register-broken"
    finally:
        ledger.close()


def test_a_tombstone_a_crash_left_beyond_the_head_is_adopted(folder, clock):
    ledger = Ledger.open(folder, clock=clock)
    register = Tombstones(ledger)
    first = register.claim(uuid4(), uuid4())
    before = (folder / LedgerStore.HEAD).read_bytes()
    second = register.claim(uuid4(), uuid4())
    ledger.close()
    # The crash came after the synced append and before the head was replaced.
    rewrite(folder / LedgerStore.HEAD, before)
    reopened = Ledger.open(folder, clock=clock)
    try:
        assert Tombstones(reopened).head() == {"sequence": 2, "digest": second["digest"]}
        assert [item["to"] for item in reopened.events("ledger.adopted")] == [2]
        assert Tombstones(reopened).by_request(first["lifecycleRequestId"]) == first
    finally:
        reopened.close()


def test_replay_lists_only_tombstones_newer_than_the_set(folder, clock):
    ledger = Ledger.open(folder, clock=clock)
    try:
        register = Tombstones(ledger)
        old = register.claim(uuid4(), uuid4())
        clock.advance(3600)
        taken = clock().astimezone(dt.UTC).isoformat(timespec="milliseconds")
        taken = taken.replace("+00:00", "Z")
        clock.advance(60)
        newer = [register.claim(uuid4(), uuid4())]
        clock.advance(60)
        newer.append(register.claim(uuid4(), uuid4()))
        replay = register.newer_than({"takenAt": taken})
        assert replay == newer and old not in replay
        assert register.newer_than({"takenAt": newer[-1]["appendedAt"]}) == [newer[-1]]
    finally:
        ledger.close()


def test_the_digest_binds_every_field():
    base = ("2026-10-22T00:00:00.000Z", "0" * 64)
    account, request = str(uuid4()), str(uuid4())
    digest = tombstone_digest(1, account, request, *base)
    assert digest != tombstone_digest(2, account, request, *base)
    assert digest != tombstone_digest(1, str(uuid4()), request, *base)
    assert digest != tombstone_digest(1, account, request, base[0], "1" * 64)
