from uuid import NAMESPACE_URL, UUID, uuid4, uuid5
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
from backend.control_worker import SET_ASIDE, ControlWorker
from backend.modules.accounts.control_cursor import ControlCursor
from backend.modules.personalization.guarded_service import GuardedSettingsService
from backend.modules.personalization.reset_repository import ResetRepository
from backend.modules.personalization.control_service import (
    PersonalizationControlService,
    ProducerBinding,
)
from backend.modules.accounts.services.control_lifecycle import ControlLifecycleService
from backend.modules.accounts.control_repository import ControlRepository

pytestmark = pytest.mark.u2_component
PASSWORD = "Synthetic!Research2026"


@pytest.fixture
def assistance_authority(entry, connect, request, fixture_discard):
    identity = entry.transactions.profile.run_id + ":cleanup:" + request.node.name
    account, session, revision = (
        uuid5(NAMESPACE_URL, identity),
        uuid5(NAMESPACE_URL, identity + ":session"),
        uuid4(),
    )
    with connect("accounts") as conn:
        conn.execute(
            "INSERT INTO accounts.account(id,email,password_hash,verified,active,authority_revision,display_name) "
            "VALUES(%s,%s,%s,true,true,%s,'Synthetic cleanup fixture') ON CONFLICT(id) DO UPDATE "
            "SET email=excluded.email,password_hash=excluded.password_hash,active=true,verified=true,"
            "lifecycle_state='active',authority_revision=excluded.authority_revision",
            (account, str(account) + "@fixture.invalid", entry._hash_password(PASSWORD), revision),
        )
        conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,authority_revision,expires_at) "
            "VALUES(%s,%s,%s,%s,%s,clock_timestamp()+interval '15 minutes') ON CONFLICT(id) DO UPDATE "
            "SET revoked=false,authority_revision=excluded.authority_revision,expires_at=excluded.expires_at",
            (session, account, str(uuid4()), str(uuid4()), revision),
        )
    yield Authority(account, session)
    fixture_discard(account)


def withdraw(entry, authority, manifest, action="withdraw"):
    service = ControlLifecycleService(entry, manifest, revision="test-current-owner-cleanup")
    profile = ControlRepository(entry.transactions, entry.control_policy).profile(authority)
    outcome = service.request(
        authority, uuid4(), UUID(profile["lifecycleRevision"]), action, PASSWORD
    )
    return service, UUID(outcome["requestId"])


def test_account_erasure_removes_private_fields_after_mail_scope(entry, assistance_authority, connect):
    authority = assistance_authority
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


def test_account_database_erasure_waits_for_private_mail_evidence(entry, assistance_authority):
    authority = assistance_authority
    service, request = withdraw(
        entry,
        authority,
        (("AccountAccess", "derived_artifacts"), ("AccountAccess", "live_records")),
        "erase",
    )
    ticket = service.claim(request, "AccountAccess", "live_records")
    with pytest.raises(Exception):
        AccountLifecycleParticipant(entry).apply(ticket)


def test_discovery_erasure_removes_private_query(entry, assistance_authority, connect):
    authority = assistance_authority
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


def test_usage_cleanup_does_not_release_accepted_responsibility(entry, assistance_authority, connect):
    authority = assistance_authority
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


def test_account_participant_rejects_foreign_scope(entry, assistance_authority):
    authority = assistance_authority
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


def test_worker_completes_installed_owner_but_keeps_missing_restore_blocked(
    entry, assistance_authority, connect
):
    authority = assistance_authority
    manifest = (("AccountAccess", "live_records"), ("ServiceOperations", "restore_enforcement"))
    service = ControlLifecycleService(entry, manifest, revision="worker-test-" + str(uuid4()))
    profile = ControlRepository(entry.transactions, entry.control_policy).profile(authority)
    accepted = service.request(
        authority, uuid4(), UUID(profile["lifecycleRevision"]), "withdraw", PASSWORD
    )
    personalization = PersonalizationControlService(
        entry.transactions,
        entry.control_policy,
        ControlCursor(b"w" * 32),
        producers=(ProducerBinding("Library"),),
    )
    worker = ControlWorker(
        entry,
        service,
        personalization,
        PrivateArtifacts(entry.transactions.profile.root / "assistance-files"),
    )
    result = worker.run_once(limit=1)
    assert result == {"requestsInspected": 1, "scopesAcknowledged": 1}
    with connect("accounts") as conn:
        rows = conn.execute(
            "SELECT participant,disposition,evidence_ref FROM accounts.lifecycle_scope "
            "WHERE request_id=%s ORDER BY participant",
            (UUID(accepted["requestId"]),),
        ).fetchall()
        assert rows[0]["participant"] == "AccountAccess" and rows[0]["disposition"] == "complete"
        assert rows[1]["disposition"] == "blocked" and rows[1]["evidence_ref"] is None
        assert (
            conn.execute(
                "SELECT disposition FROM accounts.lifecycle_request WHERE id=%s",
                (UUID(accepted["requestId"]),),
            ).fetchone()["disposition"]
            == "blocked"
        )
    assert worker.run_once(limit=1)["requestsInspected"] == 0


def test_research_consent_cleanup_restricts_results_and_replays_evidence(
    entry, assistance_authority, connect
):
    authority = assistance_authority
    files, artifact, operation = terminal_result(entry, authority, connect)
    consent_revision = uuid4()
    with connect("accounts") as conn:
        conn.execute(
            "INSERT INTO accounts.consent(account_id,purpose,granted,revision) "
            "VALUES(%s,'local-research',true,%s) ON CONFLICT(account_id,purpose) "
            "DO UPDATE SET granted=true,revision=excluded.revision",
            (authority.account_id, consent_revision),
        )
    repository = ControlRepository(entry.transactions, entry.control_policy)
    outcome = repository.update_consent(
        authority, uuid4(), consent_revision, "local-research", False
    )
    with connect("accounts") as conn:
        fact = conn.execute(
            "SELECT * FROM accounts.consent_obligation WHERE account_id=%s AND consent_revision=%s",
            (authority.account_id, UUID(outcome["revision"])),
        ).fetchone()
    service = ControlLifecycleService(
        entry, (("AccountAccess", "live_records"),), revision="consent-test"
    )
    personalization = PersonalizationControlService(
        entry.transactions,
        entry.control_policy,
        ControlCursor(b"c" * 32),
        producers=(ProducerBinding("Library"),),
    )
    worker = ControlWorker(entry, service, personalization, files)
    evidence = worker.apply_research_consent(fact)
    assert worker.apply_research_consent(fact) == evidence
    with connect("assistance") as conn:
        assert (
            conn.execute(
                "SELECT availability FROM assistance.result WHERE job_id=%s", (operation,)
            ).fetchone()["availability"]
            == "restricted"
        )
    assert (files.root / artifact.name).exists()


def assistance_files(entry):
    return PrivateArtifacts(entry.transactions.profile.root / "assistance-files")


def personalization_for(entry, label):
    return PersonalizationControlService(
        entry.transactions,
        entry.control_policy,
        ControlCursor(label * 32),
        producers=(ProducerBinding("Library"),),
    )


def grant_consents(connect, authority):
    with connect("accounts") as conn:
        for purpose in ("local-research", "personalization"):
            conn.execute(
                "INSERT INTO accounts.consent(account_id,purpose,granted) VALUES(%s,%s,true) "
                "ON CONFLICT(account_id,purpose) DO UPDATE SET granted=true",
                (authority.account_id, purpose),
            )


def research_consent_fact(entry, authority, connect):
    """Revoke local-research consent through the control repository; return its fact."""
    grant_consents(connect, authority)
    repository = ControlRepository(entry.transactions, entry.control_policy)
    current = next(
        row for row in repository.consents(authority) if row["purpose"] == "local-research"
    )
    outcome = repository.update_consent(
        authority, uuid4(), UUID(current["revision"]), "local-research", False
    )
    with connect("accounts") as conn:
        return conn.execute(
            "SELECT * FROM accounts.consent_obligation WHERE account_id=%s AND consent_revision=%s",
            (authority.account_id, UUID(outcome["revision"])),
        ).fetchone()


def test_worker_pass_requires_a_finite_bound(entry):
    service = ControlLifecycleService(
        entry, (("AccountAccess", "live_records"),), revision="bound-test"
    )
    worker = ControlWorker(entry, service, personalization_for(entry, b"b"), assistance_files(entry))
    for limit in (0, 5, True):
        with pytest.raises(ValueError, match="finite control-worker bound"):
            worker.run_once(limit=limit)


def test_account_erasure_erases_the_mail_its_proofs_name(entry, assistance_authority):
    authority = assistance_authority
    before = set(entry.mail.root.glob("*.blob"))
    entry.request_password_reset(
        uuid4(), str(authority.account_id) + "@fixture.invalid", "erasure-" + str(uuid4())
    )
    created = set(entry.mail.root.glob("*.blob")) - before
    assert len(created) == 1
    service, request = withdraw(
        entry, authority, (("AccountAccess", "derived_artifacts"),), "erase"
    )
    result = AccountLifecycleParticipant(entry).apply(
        service.claim(request, "AccountAccess", "derived_artifacts")
    )
    assert result["evidenceRef"]
    assert not any(path.exists() for path in created)


def test_usage_cleanup_revokes_the_grant_and_reports_retained_audit(
    entry, assistance_authority, connect
):
    authority = assistance_authority
    with connect("usage") as conn:
        conn.execute(
            "INSERT INTO usage.entitlement(account_id,allocation,policy) VALUES(%s,3,'u2-synthetic-v1') "
            "ON CONFLICT(account_id) DO UPDATE SET revoked=false",
            (authority.account_id,),
        )
    service, request = withdraw(entry, authority, (("UsageEntitlements", "live_records"),))
    result = UsageLifecycleParticipant(entry.transactions).apply(
        service.claim(request, "UsageEntitlements", "live_records")
    )
    assert result["reasonKey"] == "bounded-audit-identifiers-retained" and result["evidenceRef"]
    with connect("usage") as conn:
        assert conn.execute(
            "SELECT revoked FROM usage.entitlement WHERE account_id=%s", (authority.account_id,)
        ).fetchone()["revoked"]


def test_reactivation_restores_neither_usage_nor_assistance_work(
    entry, assistance_authority, connect, mailbox
):
    authority = assistance_authority
    with connect("usage") as conn:
        conn.execute(
            "INSERT INTO usage.entitlement(account_id,allocation,policy,revoked) "
            "VALUES(%s,3,'u2-synthetic-v1',true) ON CONFLICT(account_id) DO UPDATE SET revoked=true",
            (authority.account_id,),
        )
    manifest = (("PaperAssistance", "pending_work"), ("UsageEntitlements", "live_records"))
    service, _ = withdraw(entry, authority, manifest)
    flow = str(uuid4())
    entry.request_reactivation(uuid4(), str(authority.account_id) + "@fixture.invalid", flow)
    proof = next(value for value in mailbox("reactivate") if value.get("flowBinding") == flow)
    accepted = service.reactivate(uuid4(), UUID(proof["challengeId"]), proof["proof"], flow)
    identifier = UUID(accepted["requestId"])
    usage = UsageLifecycleParticipant(entry.transactions).apply(
        service.claim(identifier, "UsageEntitlements", "live_records")
    )
    work = AssistanceLifecycleParticipant(entry.transactions, assistance_files(entry)).apply(
        service.claim(identifier, "PaperAssistance", "pending_work")
    )
    assert usage["evidenceRef"] and work["evidenceRef"]
    with connect("usage") as conn:
        assert conn.execute(
            "SELECT revoked FROM usage.entitlement WHERE account_id=%s", (authority.account_id,)
        ).fetchone()["revoked"]


def test_assistance_withdrawal_restricts_results_and_keeps_their_bytes(
    entry, assistance_authority, connect
):
    authority = assistance_authority
    files, artifact, operation = terminal_result(entry, authority, connect)
    service, request = withdraw(entry, authority, (("PaperAssistance", "live_records"),))
    AssistanceLifecycleParticipant(entry.transactions, files).apply(
        service.claim(request, "PaperAssistance", "live_records")
    )
    with connect("assistance") as conn:
        assert conn.execute(
            "SELECT availability FROM assistance.result WHERE job_id=%s", (operation,)
        ).fetchone()["availability"] == "restricted"
    assert (files.root / artifact.name).exists()


def test_research_consent_evidence_refuses_a_changed_fact(entry, assistance_authority, connect):
    authority = assistance_authority
    fact = research_consent_fact(entry, authority, connect)
    service = ControlLifecycleService(entry, (("AccountAccess", "live_records"),), revision="fact-test")
    worker = ControlWorker(entry, service, personalization_for(entry, b"f"), assistance_files(entry))
    worker.apply_research_consent(fact)
    with pytest.raises(ValueError, match="consent evidence binding conflict"):
        worker.apply_research_consent(dict(fact, consent_revision=uuid4()))


def test_research_consent_waits_for_running_work(entry, assistance_authority, connect):
    authority = assistance_authority
    files, artifact, operation = terminal_result(entry, authority, connect)
    with connect("assistance") as conn:
        conn.execute("UPDATE assistance.job SET settlement_pending=true WHERE id=%s", (operation,))
    fact = research_consent_fact(entry, authority, connect)
    service = ControlLifecycleService(entry, (("AccountAccess", "live_records"),), revision="wait-test")
    worker = ControlWorker(entry, service, personalization_for(entry, b"w"), files)
    with pytest.raises(PendingLifecycleEvidence, match="consent-work-reconciliation-pending"):
        worker.apply_research_consent(fact)
    with connect("assistance") as conn:
        assert conn.execute(
            "SELECT availability FROM assistance.result WHERE job_id=%s", (operation,)
        ).fetchone()["availability"] == "retained"
        assert not conn.execute(
            "SELECT 1 FROM assistance.consent_evidence WHERE obligation_id=%s", (fact["id"],)
        ).fetchone()
        conn.execute("UPDATE assistance.job SET settlement_pending=false WHERE id=%s", (operation,))


def test_worker_skips_a_scope_another_pass_holds(entry, assistance_authority, connect):
    authority = assistance_authority
    manifest = (("AccountAccess", "live_records"), ("ServiceOperations", "restore_enforcement"))
    service = ControlLifecycleService(entry, manifest, revision="leased-" + str(uuid4()))
    profile = ControlRepository(entry.transactions, entry.control_policy).profile(authority)
    accepted = service.request(
        authority, uuid4(), UUID(profile["lifecycleRevision"]), "withdraw", PASSWORD
    )
    identifier = UUID(accepted["requestId"])
    service.claim(identifier, "AccountAccess", "live_records")
    worker = ControlWorker(entry, service, personalization_for(entry, b"l"), assistance_files(entry))
    assert worker.run_once(limit=1) == {"requestsInspected": 1, "scopesAcknowledged": 0}
    with connect("accounts") as conn:
        rows = conn.execute(
            "SELECT participant,disposition,attempts FROM accounts.lifecycle_scope "
            "WHERE request_id=%s ORDER BY participant",
            (identifier,),
        ).fetchall()
    assert rows == [
        {"participant": "AccountAccess", "disposition": "pending", "attempts": 1},
        {"participant": "ServiceOperations", "disposition": "blocked", "attempts": 1},
    ]


class SetAsideWorker(ControlWorker):
    """A worker whose hook sets every consent and lifecycle item aside for its turn."""

    def _guarded(self, kind, identity, work):
        if kind in ("consent-obligation", "lifecycle-scope"):
            return SET_ASIDE
        return work()


def test_set_aside_items_stay_open_while_resets_are_still_cleaned(
    entry, assistance_authority, connect
):
    authority = assistance_authority
    fact = research_consent_fact(entry, authority, connect)
    resets = ResetRepository(entry.transactions, entry.control_policy, ControlCursor(b"s" * 32))
    revision = GuardedSettingsService(entry.transactions).read(authority)["revision"]
    reset = resets.accept(
        authority,
        uuid4(),
        uuid4() if revision is None else UUID(revision),
        "delete_behavior",
        manifest=(("Personalization", "behavior"),),
        manifest_revision="set-aside-test",
    )
    service = ControlLifecycleService(
        entry, (("AccountAccess", "live_records"),), revision="set-aside-" + str(uuid4())
    )
    profile = ControlRepository(entry.transactions, entry.control_policy).profile(authority)
    accepted = service.request(
        authority, uuid4(), UUID(profile["lifecycleRevision"]), "withdraw", PASSWORD
    )
    personalization = PersonalizationControlService(
        entry.transactions,
        entry.control_policy,
        ControlCursor(b"s" * 32),
        producers=(ProducerBinding("Library"),),
    )
    worker = SetAsideWorker(entry, service, personalization, assistance_files(entry))
    assert worker.run_once(limit=4) == {"requestsInspected": 1, "scopesAcknowledged": 0}
    with connect("accounts") as conn:
        scope = conn.execute(
            "SELECT disposition,attempts FROM accounts.lifecycle_scope WHERE request_id=%s",
            (UUID(accepted["requestId"]),),
        ).fetchone()
        obligation = conn.execute(
            "SELECT disposition FROM accounts.consent_obligation WHERE id=%s", (fact["id"],)
        ).fetchone()
    assert scope == {"disposition": "pending", "attempts": 1}
    assert obligation["disposition"] == "pending"
    with connect("personalization") as conn:
        cleaned = conn.execute(
            "SELECT disposition FROM personalization.reset_scope WHERE reset_id=%s",
            (UUID(reset["resetId"]),),
        ).fetchone()
    assert cleaned["disposition"] == "complete"
