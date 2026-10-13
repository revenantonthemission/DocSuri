"""Actual owner effects stay fenced and never substitute for restore evidence."""

from uuid import uuid4

import pytest
from psycopg.errors import InsufficientPrivilege
from psycopg.types.json import Jsonb

from backend.modules.accounts.control_policy import SYNTHETIC_POLICY
from backend.modules.library.control_lifecycle import LibraryLifecycleParticipant
from backend.modules.personalization.control_lifecycle import PersonalizationLifecycleParticipant


@pytest.fixture
def ticket_factory(connect, authority):
    def build(participant, scope, action="erase"):
        request, revision = uuid4(), uuid4()
        with connect("accounts") as conn:
            conn.execute(
                "UPDATE accounts.account SET lifecycle_revision=%s WHERE id=%s",
                (revision, authority.account_id),
            )
            conn.execute(
                "INSERT INTO accounts.lifecycle_request(id,account_id,revision,action,policy_ref,manifest_revision,manifest,disposition,reason_key) "
                "VALUES(%s,%s,%s,%s,%s,'owner-effect-test',%s,'pending','pending')",
                (
                    request,
                    authority.account_id,
                    revision,
                    action,
                    Jsonb(SYNTHETIC_POLICY.reference),
                    Jsonb([[participant, scope]]),
                ),
            )
            conn.execute(
                "INSERT INTO accounts.lifecycle_scope(request_id,participant,scope,generation,lease_until,attempts) "
                "VALUES(%s,%s,%s,1,clock_timestamp()+interval '15 seconds',1)",
                (request, participant, scope),
            )
        return dict(
            request_id=request,
            account_id=authority.account_id,
            lifecycle_revision=revision,
            participant=participant,
            scope=scope,
            generation=1,
            action=action,
            policy_ref=SYNTHETIC_POLICY.reference,
            manifest_revision="owner-effect-test",
        )

    return build


def test_library_erases_private_records_and_receipts(
    connect, transactions, authority, ticket_factory
):
    identifier = uuid4()
    with connect("library") as conn:
        conn.execute(
            "INSERT INTO library.saved_query(account_id,id,query) VALUES(%s,%s,%s)",
            (authority.account_id, identifier, Jsonb({"private": "text"})),
        )
        conn.execute(
            "INSERT INTO library.receipt(account_id,kind,key,intent_hash,outcome) VALUES(%s,'purge-test',%s,%s,%s)",
            (authority.account_id, uuid4(), "a" * 64, Jsonb({"private": "text"})),
        )
    ticket = ticket_factory("Library", "live_records")
    result = LibraryLifecycleParticipant(transactions).apply(ticket)
    assert result["evidenceRef"] and result["disposition"] == "complete"
    with connect("library") as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM library.saved_query WHERE account_id=%s",
                (authority.account_id,),
            ).fetchone()["n"]
            == 0
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM library.receipt WHERE account_id=%s",
                (authority.account_id,),
            ).fetchone()["n"]
            == 0
        )


def test_authoritative_withdraw_cannot_be_forged_as_erase(
    connect, transactions, authority, ticket_factory
):
    with connect("library") as conn:
        identifier = uuid4()
        conn.execute(
            "INSERT INTO library.saved_query(account_id,id,query) VALUES(%s,%s,%s)",
            (authority.account_id, identifier, Jsonb({"retained": True})),
        )
    ticket = ticket_factory("Library", "live_records", "withdraw")
    LibraryLifecycleParticipant(transactions).apply(dict(ticket, action="erase"))
    with connect("library") as conn:
        assert conn.execute(
            "SELECT id FROM library.saved_query WHERE account_id=%s AND id=%s",
            (authority.account_id, identifier),
        ).fetchone()


def test_owner_effect_replay_returns_same_evidence(transactions, ticket_factory):
    participant = LibraryLifecycleParticipant(transactions)
    ticket = ticket_factory("Library", "live_records", "withdraw")
    assert participant.apply(ticket) == participant.apply(ticket)


def test_stale_and_foreign_scope_denied(transactions, ticket_factory):
    participant = LibraryLifecycleParticipant(transactions)
    ticket = ticket_factory("Library", "live_records", "withdraw")
    with pytest.raises(InsufficientPrivilege):
        participant.apply(dict(ticket, generation=2))
    with pytest.raises(PermissionError):
        participant.apply(dict(ticket, participant="Personalization"))
    with pytest.raises(PermissionError):
        participant.apply(dict(ticket, scope="restore_enforcement"))


def test_superseded_lifecycle_ticket_cannot_apply(connect, transactions, authority, ticket_factory):
    ticket = ticket_factory("Library", "live_records", "withdraw")
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.account SET lifecycle_revision=%s WHERE id=%s",
            (uuid4(), authority.account_id),
        )
    with pytest.raises(InsufficientPrivilege):
        LibraryLifecycleParticipant(transactions).apply(ticket)


def test_personalization_erases_settings_and_private_receipts(
    connect, transactions, authority, ticket_factory
):
    with connect("personalization") as conn:
        conn.execute(
            "INSERT INTO personalization.settings(account_id,defaults) VALUES(%s,'{}') ON CONFLICT DO NOTHING",
            (authority.account_id,),
        )
        conn.execute(
            "INSERT INTO personalization.receipt(account_id,kind,key,intent_hash,outcome) VALUES(%s,'purge-test',%s,%s,%s)",
            (authority.account_id, uuid4(), "a" * 64, Jsonb({"private": "interest"})),
        )
    ticket = ticket_factory("Personalization", "live_records")
    PersonalizationLifecycleParticipant(transactions).apply(ticket)
    with connect("personalization") as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM personalization.settings WHERE account_id=%s",
                (authority.account_id,),
            ).fetchone()["n"]
            == 0
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM personalization.receipt WHERE account_id=%s",
                (authority.account_id,),
            ).fetchone()["n"]
            == 0
        )


def test_personalization_derived_scope_leaves_explicit_settings(
    connect, transactions, authority, ticket_factory
):
    with connect("personalization") as conn:
        conn.execute(
            "INSERT INTO personalization.settings(account_id,defaults) VALUES(%s,'{}') ON CONFLICT DO NOTHING",
            (authority.account_id,),
        )
        conn.execute(
            "INSERT INTO personalization.behavior(account_id,id,purpose_revision,fact) VALUES(%s,%s,%s,'{}')",
            (authority.account_id, uuid4(), uuid4()),
        )
    ticket = ticket_factory("Personalization", "derived_artifacts")
    PersonalizationLifecycleParticipant(transactions).apply(ticket)
    with connect("personalization") as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM personalization.behavior WHERE account_id=%s",
                (authority.account_id,),
            ).fetchone()["n"]
            == 0
        )
        assert conn.execute(
            "SELECT account_id FROM personalization.settings WHERE account_id=%s",
            (authority.account_id,),
        ).fetchone()


def test_receipt_purge_requires_actual_erasure(connect, authority, ticket_factory):
    ticket = ticket_factory("Personalization", "live_records", "withdraw")
    with connect("personalization") as conn, pytest.raises(InsufficientPrivilege):
        conn.execute(
            "SELECT personalization.erase_private_controls(%s,%s,%s,%s,%s)",
            (
                ticket["request_id"],
                authority.account_id,
                ticket["generation"],
                Jsonb(ticket["policy_ref"]),
                ticket["manifest_revision"],
            ),
        )
