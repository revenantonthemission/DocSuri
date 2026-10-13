from uuid import UUID, uuid4
import pytest

from backend.control_worker import (
    AccountLifecycleParticipant,
    DiscoveryLifecycleParticipant,
    UsageLifecycleParticipant,
    PendingLifecycleEvidence,
    AssistanceLifecycleParticipant,
)
from backend.artifacts import PrivateArtifacts
from backend.transactions import Authority
from backend.modules.accounts.services.control_lifecycle import ControlLifecycleService
from backend.modules.accounts.control_repository import ControlRepository

pytestmark = pytest.mark.u2_component
PASSWORD = "Synthetic!Research2026"


@pytest.fixture
def assistance_authority(entry, connect):
    account, session, revision = uuid4(), uuid4(), uuid4()
    with connect("accounts") as conn:
        conn.execute(
            "INSERT INTO accounts.account(id,email,password_hash,verified,active,authority_revision,display_name) "
            "VALUES(%s,%s,%s,true,true,%s,'Synthetic cleanup fixture')",
            (account, str(account) + "@fixture.invalid", entry._hash_password(PASSWORD), revision),
        )
        conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,authority_revision,expires_at) "
            "VALUES(%s,%s,%s,%s,%s,clock_timestamp()+interval '15 minutes')",
            (session, account, str(uuid4()), str(uuid4()), revision),
        )
    return Authority(account, session)


def withdraw(entry, authority, manifest, action="withdraw"):
    service = ControlLifecycleService(entry, manifest, revision="test-current-owner-cleanup")
    profile = ControlRepository(entry.transactions, entry.control_policy).profile(authority)
    outcome = service.request(
        authority, uuid4(), UUID(profile["lifecycleRevision"]), action, PASSWORD
    )
    return service, UUID(outcome["requestId"])


def test_account_erasure_removes_private_fields_after_mail_scope(entry, authority, connect):
    service, request = withdraw(
        entry,
        authority,
        (("AccountAccess", "derived_artifacts"), ("AccountAccess", "live_records")),
        "erase",
    )
    adapter = AccountLifecycleParticipant(entry)
    for scope in ("derived_artifacts", "live_records"):
        ticket = service.claim(request, "AccountAccess", scope)
        result = adapter.apply(ticket)
        service.acknowledge(
            ticket, evidence=UUID(result["evidenceRef"]), reason=result["reasonKey"]
        )
    with connect("accounts") as conn:
        row = conn.execute(
            "SELECT email,password_hash,profile FROM accounts.account WHERE id=%s",
            (authority.account_id,),
        ).fetchone()
        assert (
            row["email"].endswith("@erased.invalid")
            and row["password_hash"] == "!erased"
            and row["profile"] == {}
        )
        assert not conn.execute(
            "SELECT 1 FROM accounts.identity_link WHERE account_id=%s", (authority.account_id,)
        ).fetchone()


def test_account_database_erasure_waits_for_private_mail_evidence(entry, authority):
    service, request = withdraw(
        entry,
        authority,
        (("AccountAccess", "derived_artifacts"), ("AccountAccess", "live_records")),
        "erase",
    )
    ticket = service.claim(request, "AccountAccess", "live_records")
    with pytest.raises(Exception):
        AccountLifecycleParticipant(entry).apply(ticket)


def test_discovery_erasure_removes_private_query(entry, authority, connect):
    with connect("discovery") as conn:
        conn.execute(
            "INSERT INTO discovery.execution(id,account_id,query,query_hash,results,relay_state) VALUES(%s,%s,'{\"query\":\"private topic\"}',%s,'[]','none')",
            (uuid4(), authority.account_id, "a" * 64),
        )
    service, request = withdraw(
        entry, authority, (("DiscoveryCitations", "live_records"),), "erase"
    )
    result = DiscoveryLifecycleParticipant(entry.transactions).apply(
        service.claim(request, "DiscoveryCitations", "live_records")
    )
    assert result["evidenceRef"]
    with connect("discovery") as conn:
        assert not conn.execute(
            "SELECT 1 FROM discovery.execution WHERE account_id=%s", (authority.account_id,)
        ).fetchone()


def test_usage_cleanup_does_not_release_accepted_responsibility(entry, authority, connect):
    with connect("usage") as conn:
        conn.execute(
            "INSERT INTO usage.entitlement(account_id,allocation,policy) VALUES(%s,3,'u2-synthetic-v1') ON CONFLICT DO NOTHING",
            (authority.account_id,),
        )
        conn.execute(
            "INSERT INTO usage.reservation(id,account_id,operation_id,intent_hash,disposition) VALUES(%s,%s,%s,%s,'reserved')",
            (uuid4(), authority.account_id, uuid4(), "e" * 64),
        )
    service, request = withdraw(entry, authority, (("UsageEntitlements", "live_records"),))
    with pytest.raises(PendingLifecycleEvidence):
        UsageLifecycleParticipant(entry.transactions).apply(
            service.claim(request, "UsageEntitlements", "live_records")
        )
    with connect("usage") as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM usage.reservation WHERE account_id=%s AND disposition='reserved'",
                (authority.account_id,),
            ).fetchone()["n"]
            > 0
        )


def test_account_participant_rejects_foreign_scope(entry, authority):
    service, request = withdraw(entry, authority, (("AccountAccess", "live_records"),))
    ticket = service.claim(request, "AccountAccess", "live_records")
    ticket["scope"] = "backups"
    with pytest.raises(PermissionError):
        AccountLifecycleParticipant(entry).apply(ticket)


def terminal_result(entry, authority, connect):
    files = PrivateArtifacts(entry.transactions.profile.root / "assistance-files")
    artifact = files.publish(b"Synthetic private assistance result")
    operation, reservation = uuid4(), uuid4()
    with connect("assistance") as conn:
        conn.execute(
            "INSERT INTO assistance.admission(operation_id,account_id,intent_hash,intent,disposition,reservation_id) "
            "VALUES(%s,%s,%s,'{}','accepted',%s)",
            (operation, authority.account_id, "d" * 64, reservation),
        )
        conn.execute(
            "INSERT INTO assistance.job(id,account_id,authority_revision,version_id,source_hash,input_hash,"
            "payload,glossary_revision,glossary_snapshot,reservation_id,state,dispatch_pending) "
            "VALUES(%s,%s,%s,'synthetic-version',%s,%s,'{}','empty','{}',%s,'succeeded',false)",
            (operation, authority.account_id, uuid4(), "a" * 64, "b" * 64, reservation),
        )
        conn.execute(
            "INSERT INTO assistance.result(id,job_id,account_id,version_id,input_hash,source_hash,output_hash,"
            "private_path,byte_length,coverage,provenance,availability) VALUES(%s,%s,%s,'synthetic-version',%s,%s,%s,%s,%s,'{}','{}','retained')",
            (
                uuid4(),
                operation,
                authority.account_id,
                "b" * 64,
                "a" * 64,
                artifact.sha256,
                artifact.name,
                artifact.size,
            ),
        )
    return files, artifact, operation


def test_assistance_erasure_deletes_bytes_and_keeps_acceptance_fence(
    entry, assistance_authority, connect
):
    authority = assistance_authority
    files, artifact, operation = terminal_result(entry, authority, connect)
    service, request = withdraw(
        entry,
        authority,
        (("PaperAssistance", "derived_artifacts"), ("PaperAssistance", "live_records")),
        "erase",
    )
    adapter = AssistanceLifecycleParticipant(entry.transactions, files)
    for scope in ("derived_artifacts", "live_records"):
        ticket = service.claim(request, "PaperAssistance", scope)
        result = adapter.apply(ticket)
        # Lost acknowledgement replays durable evidence, including after file deletion.
        assert adapter.apply(ticket) == result
        service.acknowledge(
            ticket, evidence=UUID(result["evidenceRef"]), reason=result["reasonKey"]
        )
    assert not (files.root / artifact.name).exists()
    with connect("assistance") as conn:
        assert not conn.execute(
            "SELECT 1 FROM assistance.result WHERE account_id=%s", (authority.account_id,)
        ).fetchone()
        assert not conn.execute(
            "SELECT 1 FROM assistance.job WHERE account_id=%s", (authority.account_id,)
        ).fetchone()
        fence = conn.execute(
            "SELECT * FROM assistance.erased_admission WHERE operation_id=%s", (operation,)
        ).fetchone()
        assert fence["disposition"] == "accepted" and fence["erased_by"] == request


def test_assistance_erasure_waits_for_settlement_and_file_evidence(
    entry, assistance_authority, connect
):
    authority = assistance_authority
    files, artifact, operation = terminal_result(entry, authority, connect)
    with connect("assistance") as conn:
        conn.execute("UPDATE assistance.job SET settlement_pending=true WHERE id=%s", (operation,))
    service, request = withdraw(
        entry,
        authority,
        (("PaperAssistance", "derived_artifacts"), ("PaperAssistance", "live_records")),
        "erase",
    )
    adapter = AssistanceLifecycleParticipant(entry.transactions, files)
    ticket = service.claim(request, "PaperAssistance", "derived_artifacts")
    with pytest.raises(PendingLifecycleEvidence):
        adapter.apply(ticket)
    assert (files.root / artifact.name).exists()
    with connect("assistance") as conn:
        conn.execute("UPDATE assistance.job SET settlement_pending=false WHERE id=%s", (operation,))
    with pytest.raises(Exception):
        adapter.apply(service.claim(request, "PaperAssistance", "live_records"))
    assert (files.root / artifact.name).exists()
