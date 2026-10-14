"""A retained real-store proof remains readable across controlled key rotation."""

from uuid import uuid4

import pytest

from backend.modules.accounts.control_policy import SYNTHETIC_POLICY
from backend.modules.accounts.control_key_recovery import capture, recover
from backend.modules.accounts.services.control_entry import ControlEntryService

pytestmark = pytest.mark.u2_operations


def test_stored_proofs_keep_exact_envelope_versions_after_rotation(
    transactions, identities, connect
):
    entry = ControlEntryService(transactions, SYNTHETIC_POLICY)
    before = uuid4()
    custody_name = uuid4().hex + ".blob"
    ciphertext = entry.protect("proof:" + str(before), {"delivery": custody_name})
    version = entry.protection_version(ciphertext)
    with connect("accounts") as conn:
        conn.execute(
            "INSERT INTO accounts.control_proof(id,account_id,purpose,proof_hash,flow_hash,authority_revision,lifecycle_revision,protected_payload,key_version,expires_at) "
            "SELECT %s,id,'password-reset',%s,%s,authority_revision,lifecycle_revision,%s,%s,clock_timestamp()+interval '1 minute' FROM accounts.account WHERE id=%s",
            (before, uuid4().hex * 2, uuid4().hex * 2, ciphertext, version, identities["a"]),
        )
    # The owned run rotates once. Later verification reuses retained custody;
    # it neither removes old keys nor spends another finite rotation slot.
    if entry.keyring.read()["generation"] == 1:
        entry.keyring.rotate()
    custody = capture(entry.keyring)
    recovered = recover(
        transactions.profile.root,
        transactions.profile.run_id,
        expected_digest=custody["digest"],
        expected_generation=custody["generation"],
    )
    assert recovered["digest"] == custody["digest"]
    restarted = ControlEntryService(transactions, SYNTHETIC_POLICY)
    with connect("accounts") as conn:
        stored = conn.execute(
            "SELECT protected_payload,key_version FROM accounts.control_proof WHERE id=%s",
            (before,),
        ).fetchone()
    assert stored["key_version"] == version
    assert restarted.reveal("proof:" + str(before), stored["protected_payload"]) == {
        "delivery": custody_name
    }
    fresh = restarted.protect("proof:new", {"ok": True})
    assert restarted.protection_version(fresh) == restarted.keyring.active_version
    assert restarted.reveal("proof:new", fresh) == {"ok": True}
