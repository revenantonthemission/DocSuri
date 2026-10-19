"""Persistent invariants tested through least-privileged owner roles."""
from uuid import uuid4

import psycopg
import pytest

pytestmark = pytest.mark.u2_database


def reset(conn, owner):
    identifier = uuid4()
    boundary = int.from_bytes(identifier.bytes[:7], "big")
    conn.execute("INSERT INTO personalization.reset_responsibility(id,account_id,action,accepted_settings_revision,"
        "input_boundary,policy_ref,manifest_revision,disposition,reason_key) "
        "VALUES(%s,%s,'delete_behavior',%s,%s,'{\"policyId\":\"u2-synthetic-v1\",\"revision\":\"1\"}',"
        "'installed-u2-v1','pending','pending')", (identifier, owner, uuid4(), boundary))
    return identifier


def test_cross_owner_writer_denied(connect, identities):
    with connect("library") as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("UPDATE accounts.account SET display_name='forged' WHERE id=%s", (identities["a"],))


def test_provider_subject_unique_across_owners(connect, identities):
    with connect("accounts") as conn:
        subject = str(uuid4())
        conn.execute("INSERT INTO accounts.identity_link(id,account_id,provider,subject) VALUES(%s,%s,'google',%s)",
            (uuid4(), identities["a"], subject))
        with pytest.raises(psycopg.errors.UniqueViolation):
            conn.execute("INSERT INTO accounts.identity_link(id,account_id,provider,subject) VALUES(%s,%s,'google',%s)",
                (uuid4(), identities["b"], subject))


def test_limited_session_cannot_use_owner_guard(connect, identities):
    with connect("accounts") as conn:
        conn.execute("UPDATE accounts.session SET purpose='primary_mfa_continuation' WHERE id=%s", (identities["session"],))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT accounts.guard_session(%s,%s,'account-control')", (identities["a"], identities["session"]))


def test_account_controls_do_not_require_optional_consent(connect, identities):
    with connect("accounts") as conn:
        conn.execute("UPDATE accounts.consent SET granted=false WHERE account_id=%s", (identities["a"],))
        result = conn.execute("SELECT accounts.guard_session(%s,%s,'account-control') AS revision",
            (identities["a"], identities["session"])).fetchone()
        assert result["revision"] == identities["revision"]


def test_administration_requires_fresh_mfa(connect, identities):
    with connect("accounts") as conn:
        conn.execute("UPDATE accounts.account SET role='administrator' WHERE id=%s", (identities["a"],))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT accounts.guard_session(%s,%s,'administration')", (identities["a"], identities["session"]))


def test_administrator_with_fresh_mfa_passes(connect, identities):
    with connect("accounts") as conn:
        conn.execute("UPDATE accounts.account SET role='administrator' WHERE id=%s", (identities["a"],))
        conn.execute("UPDATE accounts.session SET mfa_at=clock_timestamp() WHERE id=%s", (identities["session"],))
        assert conn.execute("SELECT accounts.guard_session(%s,%s,'administration') AS revision",
            (identities["a"], identities["session"])).fetchone()["revision"] == identities["revision"]


def test_reset_acceptance_is_immutable(connect, identities):
    with connect("personalization") as conn:
        identifier = reset(conn, identities["a"])
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("UPDATE personalization.reset_responsibility SET accepted_at=clock_timestamp() WHERE id=%s", (identifier,))


def test_reset_status_requires_monotonic_revision(connect, identities):
    with connect("personalization") as conn:
        identifier = reset(conn, identities["a"])
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("UPDATE personalization.reset_responsibility SET disposition='blocked' WHERE id=%s", (identifier,))


def test_reset_complete_cannot_regress(connect, identities):
    with connect("personalization") as conn:
        identifier = reset(conn, identities["a"])
        conn.execute("UPDATE personalization.reset_responsibility SET disposition='complete',status_revision=2 WHERE id=%s", (identifier,))
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("UPDATE personalization.reset_responsibility SET disposition='pending',status_revision=3 WHERE id=%s", (identifier,))


def test_lifecycle_complete_scope_requires_evidence(connect, identities):
    with connect("accounts") as conn:
        request = uuid4()
        conn.execute("INSERT INTO accounts.lifecycle_request(id,account_id,revision,action,policy_ref,manifest_revision,manifest,disposition,reason_key) "
            "VALUES(%s,%s,%s,'withdraw','{}','installed-u2-v1','[\"library\"]','pending','pending')", (request, identities["a"], uuid4()))
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("INSERT INTO accounts.lifecycle_scope(request_id,participant,scope,disposition) VALUES(%s,'Library','references','complete')", (request,))


def test_proof_consumption_needs_operation_binding(connect, identities):
    with connect("accounts") as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("INSERT INTO accounts.control_proof(id,account_id,purpose,proof_hash,flow_hash,authority_revision,lifecycle_revision,"
                "expires_at,consumed_at) VALUES(%s,%s,'password-reset',%s,%s,%s,%s,clock_timestamp(),clock_timestamp())",
                (uuid4(), identities["a"], 'a'*64, 'b'*64, identities["revision"], uuid4()))


def test_quota_cannot_be_unlimited(connect, identities):
    with connect("usage") as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("INSERT INTO usage.entitlement(account_id,allocation,policy) VALUES(%s,100000,'u2-synthetic-v1')", (uuid4(),))


def test_owner_effect_lock_serializes_session_revocation(connect, identities):
    effect, revoker = connect('library'), connect('accounts')
    effect.execute("SELECT accounts.guard_session(%s,%s,'account-control')", (identities['a'], identities['session']))
    revoker.execute("SET LOCAL lock_timeout='100ms'")
    with pytest.raises(psycopg.errors.LockNotAvailable):
        revoker.execute("UPDATE accounts.session SET revoked=true WHERE id=%s", (identities['session'],))
    revoker.rollback()
    effect.commit()
    revoker.execute("UPDATE accounts.session SET revoked=true WHERE id=%s", (identities['session'],))
    revoker.commit()
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        effect.execute("SELECT accounts.guard_session(%s,%s,'account-control')", (identities['a'], identities['session']))
    effect.rollback()
