"""Actual account, corpus, admission and payload; no inference or useful-output claim.

Retain each fresh operation and release only after a conclusive guarded failure.
The account is journey A, leaving the second account for isolation scenarios.
"""

import hashlib
import json
import secrets
from uuid import UUID, NAMESPACE_URL, uuid4, uuid5

import pytest

from backend.artifacts import Artifact, PrivateArtifacts
from backend.local_profile import private_bytes
from backend.modules.accounts.services.guarded_entry import GuardedEntryService
from backend.modules.corpus.repository import CorpusRepository, content_revision
from backend.modules.plans.guarded_repository import GuardedUsageRepository
from backend.modules.summarization.admission import AssistanceAdmission
from backend.modules.summarization.execution import ExecutionClaims
from backend.modules.summarization.guarded_repository import GuardedAssistanceRepository
from backend.modules.summarization.payload import ExecutionPayloads
from backend.modules.summarization.requests import (
    AssistanceCatalog,
    AssistanceRequests,
    PROCESSING_POLICY,
)
from backend.transactions import OwnerTransactions
from docsuri_shared.workspace import execution as wire
from scripts.verify_docsuri_u1 import private_json

pytestmark = pytest.mark.u1_repository


class PrivateRecord(dict):
    def __repr__(self):
        return "<protected synthetic fixture identity>"


def journey_account(tx):
    profile = tx.profile
    path = profile.root / "journey-account-a.json"
    email = "journey-a@fixture.invalid"
    rows = tx.run(
        "accounts",
        lambda conn: conn.execute(
            "SELECT id,email,verified FROM accounts.account ORDER BY id LIMIT 3"
        ).fetchall(),
    )
    if len(rows) > 2:
        raise AssertionError("journey account allocation exceeded")
    existing = next((row for row in rows if row["email"] == email), None)
    if path.exists():
        identity = PrivateRecord(json.loads(private_bytes(path, maximum=4096)))
        if (
            identity["runId"] != profile.run_id
            or identity["database"] != profile.database_name
            or identity["email"] != email
        ):
            raise AssertionError("journey account fixture custody differs")
    else:
        if existing or len(rows) >= 2:
            raise AssertionError("unknown existing identity or no free account allocation")
        identity = PrivateRecord(
            {
                "runId": profile.run_id,
                "database": profile.database_name,
                "email": email,
                "password": secrets.token_urlsafe(32) + "1!aA",
                "flow": secrets.token_urlsafe(32),
            }
        )
        private_json(path, identity)
    entry = GuardedEntryService(tx)
    if not existing:
        entry.register(
            uuid5(NAMESPACE_URL, profile.run_id + ":journey-a-register"),
            email,
            identity["password"],
            "연구자 A",
            identity["flow"],
        )
    if not existing or not existing["verified"]:
        delivery = tx.run(
            "accounts",
            lambda conn: conn.execute(
                "SELECT d.* FROM accounts.delivery d JOIN accounts.challenge c ON c.id=d.challenge_id "
                "JOIN accounts.account a ON a.id=c.account_id WHERE a.email=%s AND NOT c.consumed "
                "ORDER BY c.expires_at DESC LIMIT 1",
                (email,),
            ).fetchone(),
        )
        if not delivery:
            raise AssertionError("synthetic verification delivery unavailable")
        proof = PrivateRecord(
            json.loads(
                entry.mail.read(
                    Artifact(
                        delivery["private_path"],
                        delivery["content_hash"],
                        delivery["byte_length"],
                    )
                )
            )
        )
        entry.verify_email(
            UUID(proof["challengeId"]),
            proof["proof"],
            identity["flow"],
            operation=uuid5(NAMESPACE_URL, profile.run_id + ":journey-a-verify"),
        )
    session = entry.login(email, identity["password"])
    return entry, entry.authenticate(session.token, csrf=session.csrf)


def test_actual_canonical_span_payload_and_guarded_release(realm):
    profile = realm[0].journey()
    tx = OwnerTransactions(profile)
    entry = authority = None
    try:
        entry, authority = journey_account(tx)
        jobs = tx.run(
            "assistance",
            lambda conn: conn.execute(
                "SELECT id,state,payload FROM assistance.job WHERE account_id=%s LIMIT 65",
                (authority.account_id,),
            ).fetchall(),
        )
        if len(jobs) >= 64 or any(row["state"] in {"accepted", "running"} for row in jobs):
            raise AssertionError(
                "journey diagnostic history full or outstanding work needs reconciliation"
            )
        tx.run(
            "usage",
            lambda conn: conn.execute(
                "INSERT INTO usage.entitlement(account_id,allocation,policy) VALUES(%s,4,'synthetic-four-no-reset') "
                "ON CONFLICT DO NOTHING",
                (authority.account_id,),
            ),
        )
        corpus = CorpusRepository(
            tx, PrivateArtifacts(profile.root / "corpus-files", maximum_bytes=2097152)
        )
        source = corpus.read("1706.03762v7")
        chunk = next(c for c in source["content"]["chunks"] if c["anchor"] == "s3.5.p1")
        selected = {
            "anchor": chunk["anchor"],
            "heading": chunk["section"],
            "textHash": chunk["textHash"],
            "start": 227,
            "end": 343,
            "selectedHash": hashlib.sha256(chunk["text"][227:343].encode()).hexdigest(),
        }
        definitions = [
            {
                "option": {
                    "optionId": "diagnostic-canonical-ko-span",
                    "operation": "translation",
                    "sourceLanguageId": "en",
                    "targetLanguageId": "ko",
                    "presentationLevelId": "selected-source",
                    "labelKey": "assistance.selectedTranslation",
                },
                "selectedSections": [selected],
            }
        ]
        # Explicit test-only readiness injection exercises transport binding;
        # no normal adapter is enabled and no model result is produced.
        catalog = AssistanceCatalog(source, definitions, quality_ready=True)
        pa = GuardedAssistanceRepository(tx, PrivateArtifacts(profile.root / "assistance-files"))
        usage = GuardedUsageRepository(tx)
        admission = AssistanceAdmission(pa, usage)
        glossary = tx.run(
            "assistance",
            lambda conn: conn.execute(
                "SELECT * FROM assistance.read_glossary(%s)", (authority.account_id,)
            ).fetchone(),
        )
        request = {
            "paper": catalog.paper,
            "contentRevision": content_revision(source),
            "contentHash": source["source_hash"],
            "operation": "translation",
            "optionId": "diagnostic-canonical-ko-span",
            "optionsRevision": catalog.revision,
            "glossaryRevision": glossary["revision"],
            "processingPolicy": PROCESSING_POLICY,
        }
        operation, worker = uuid4(), uuid4()
        job = AssistanceRequests(admission, corpus, lambda _: catalog).submit(
            authority, operation, request
        )
        claims = ExecutionClaims(pa)
        acquired = claims.acquire(claims.binding(job), worker)
        try:
            reader = ExecutionPayloads(claims, corpus)
            payload = reader.read(acquired["claim"], trusted_worker=worker)
            assert (
                wire.AssistanceExecutionPayload.model_validate(payload).binding.inputHash.root
                == job["input_hash"]
            )
            assert payload["sections"][0]["text"] == chunk["text"][227:343]
            assert payload["sections"][0]["sectionId"] == "s3.5.p1:227:343"
            with pytest.raises(PermissionError):
                reader.read(acquired["claim"], trusted_worker=uuid4())
        finally:
            # Explicitly no executor exists for this diagnostic operation. This
            # owner fact, not elapsed time, permits releasing the reservation.
            proposal = claims.proposal(
                acquired["claim"],
                input_hash=job["input_hash"],
                expected_job_revision=acquired["jobRevision"],
            )
            pa.fail(proposal, uuid5(operation, "diagnostic-no-executor"), "dependency-unavailable")
            admission.settle_terminal(operation)
        assert usage.reservation(authority, operation)["disposition"] == "released"
        assert pa.snapshot(authority, operation)["state"] == "failed"
        assert (
            tx.run(
                "assistance",
                lambda conn: conn.execute(
                    "SELECT count(*) AS count FROM assistance.result WHERE job_id=%s", (operation,)
                ).fetchone()["count"],
            )
            == 0
        )
    finally:
        try:
            if entry is not None and authority is not None:
                entry.logout(authority)
        finally:
            tx.close()
