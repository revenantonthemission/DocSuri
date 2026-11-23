"""The lifecycle manifest across every participant (U8 plan Step 18; BR2.1-BR2.7).

Requests are made through AccountAccess's `CompleteLifecycleService` and driven by the
complete assembly's `CompleteLifecycleWorker` with all ten participants, in the
composed realm. Each test uses its own deterministic synthetic account, reset through
the accounts owner's login as the conftest's accounts are, so the realm's 20-account
budget holds across runs; a test's next run supersedes its earlier request by starting a
new one. A request whose open parts all wait on ServiceOperations is passed over by the
worker (your decision of 2026-10-22, `test_waiting_parts.py`), so a request a test leaves
waiting never holds back a later test's. AccountAccess's claim lease is a database-clock
lease; where a test needs a second claim, it moves that lease into the past through the
accounts owner's login instead of waiting for it.
"""

from __future__ import annotations

import datetime as dt
from uuid import uuid4

import pytest

from backend.modules.accounts.password import get_password_hasher
from backend.modules.operations.ledger import utc_text
from backend.modules.operations.tombstones import Tombstones
from backend.modules.research.execution import ResearchExecution, binding
from backend.modules.research.jobs import ResearchJobs
from backend.modules.topics.repository import TopicsRepository
from backend.transactions import Authority
from backend.u8_host import (
    LifecycleManifestRefused,
    compose,
    configure_lifecycle,
    lifecycle_worker,
)
from backend.u8_registry import (
    CAPABILITIES,
    CONTRIBUTIONS,
    LIFECYCLE_MANIFEST,
    LIFECYCLE_REVISION,
    MODEL_EVIDENCE,
    NAVIGATION,
    PARTICIPANT_COMPONENTS,
    Manifest,
)
from tests.u6_approved_export import store_flows as export_flows
from tests.u8_service_operations_integration.conftest import _make_account

PASSWORD = "synthetic-lifecycle-" + uuid4().hex[:12]  # per run (L1-36)


@pytest.fixture
def composition(realm):
    value = compose(realm, process="workers")
    yield value
    value.close()


@pytest.fixture
def lifecycle_account(connect, realm):
    """A fresh-state account of the test's own, deterministic by its suffix so the
    realm's account budget holds, with a password it can reauthenticate with."""

    def make(suffix: str) -> Authority:
        authority = _make_account(connect, realm, suffix=suffix)
        with connect("accounts") as conn:
            conn.execute(
                "UPDATE accounts.account SET lifecycle_state='active',active=true,"
                "password_hash=%s WHERE id=%s",
                (get_password_hasher().hash(PASSWORD), authority.account_id),
            )
        return authority

    return make


def lifecycle_revision(connect, account):
    with connect("accounts") as conn:
        return conn.execute("SELECT lifecycle_revision FROM accounts.account WHERE id=%s",
                            (account,)).fetchone()["lifecycle_revision"]


def scopes(connect, request) -> dict:
    with connect("accounts") as conn:
        rows = conn.execute(
            "SELECT participant,scope,disposition,reason_key,attempts FROM "
            "accounts.lifecycle_scope WHERE request_id=%s", (request,)).fetchall()
    return {(row["participant"], row["scope"]): row for row in rows}


def request_row(connect, request) -> dict:
    with connect("accounts") as conn:
        return conn.execute("SELECT * FROM accounts.lifecycle_request WHERE id=%s",
                            (request,)).fetchone()


def expire_leases(connect, request) -> None:
    with connect("accounts") as conn:
        conn.execute("UPDATE accounts.lifecycle_scope SET lease_until=clock_timestamp()-"
                     "interval '1 second' WHERE request_id=%s AND disposition<>'complete'",
                     (request,))


def drive(worker, passes: int = 4) -> None:
    for _ in range(passes):
        worker.run_once(limit=4)


def start(composition, connect, authority, action: str):
    service = composition.parts["account-controls"]["lifecycle"]
    outcome = service.request(authority, uuid4(),
                              lifecycle_revision(connect, authority.account_id), action,
                              PASSWORD)
    return outcome["requestId"]


# --- 1. A manifest missing a participant or scope -----------------------------------------


def test_a_manifest_missing_a_participant_or_scope_is_refused(composition, realm):
    entry = composition.parts["account-controls"]["entry"]
    for pairs in (LIFECYCLE_MANIFEST[:-1], LIFECYCLE_MANIFEST + (("Library", "caches"),),
                  LIFECYCLE_MANIFEST + LIFECYCLE_MANIFEST[:1],
                  tuple(p for p in LIFECYCLE_MANIFEST if p[0] != "ResearchWorkspace")):
        with pytest.raises(LifecycleManifestRefused):
            configure_lifecycle(entry, pairs)
    service = configure_lifecycle(entry, LIFECYCLE_MANIFEST)
    assert (len(service.manifest), service.revision) == (21, LIFECYCLE_REVISION)
    # Composed with a manifest that lacks a pair, AccountAccess's controls are refused as
    # incompatible: no lifecycle service exists, so no request can start under it.
    short = Manifest(CONTRIBUTIONS, CAPABILITIES, NAVIGATION, LIFECYCLE_MANIFEST[:-1],
                     MODEL_EVIDENCE).sealed().verify()
    refused = compose(realm, manifest=short, process="workers")
    try:
        assert refused.activations["account-controls"].reason == "incompatible"
        assert "account-controls" not in refused.parts
        assert refused.worker.lifecycle is None
    finally:
        refused.close()
    # Every pair has its participant's adapter, and each participant has C02's component.
    worker = composition.worker.lifecycle
    components = c02_participant_components()
    for participant, scope in LIFECYCLE_MANIFEST:
        assert scope in worker.participants[participant].scopes
        assert PARTICIPANT_COMPONENTS[participant] in components
    assert PARTICIPANT_COMPONENTS["DiscoveryCitations"] == "Discovery"
    assert "DiscoveryCitations" not in components


def c02_participant_components() -> set[str]:
    """C02 `LifecycleParticipant.component`'s enum, read from the canonical source."""
    import re
    from pathlib import Path

    source = (Path(__file__).resolve().parents[3] / "aidlc/spaces/default/intents/"
              "261010-docsuri-v2-rebuild/inception/contract-design/contract-summary.md")
    text = source.read_text()
    start = text.index("  LifecycleParticipant: {type: object")
    found = re.search(r"component: \{type: string, enum: \[([^\]]*)\]", text[start:])
    return {name.strip() for name in found.group(1).split(",")}


# --- 2. Withdraw stops work, including work in flight ----------------------------------


def research_work(transactions, authority) -> list:
    jobs = ResearchJobs(transactions)
    context = jobs.create_context(authority, "novelty")
    value = {"scope": {"contextId": str(context["id"]), "publicPapers": [],
                       "attachmentIds": [], "webReferences": [], "scopePolicy": {}},
             "text": "synthetic", "policy": {}}
    accepted = [jobs.accept(authority, kind="novelty-analysis", operation_key=str(uuid4()),
                            value=value, usage_id=uuid4()) for _ in range(2)]
    running = ResearchExecution(transactions, None)
    running.acquireExecutionClaim(authority, binding(accepted[1]), uuid4())
    return [row["id"] for row in accepted]


def test_withdraw_stops_research_digests_and_exports_including_work_in_flight(
    composition, connect, transactions, lifecycle_account,
):
    authority = lifecycle_account("lifecycle-withdraw")
    job_ids = research_work(transactions, authority)
    topic = TopicsRepository(transactions).follow(
        authority, f"topic-{uuid4().hex[:8]}", "Synthetic topic")["topic"]
    exports = export_flows.repository(transactions)
    now = dt.datetime.now(dt.UTC)
    connection = export_flows.connected(exports, connect, authority, now)
    effect = export_flows.bound(exports, authority, connection, now)["effect"]
    with connect("research") as conn:
        before = conn.execute("SELECT id,state,fence FROM research.job WHERE id=ANY(%s)",
                              (job_ids,)).fetchall()
    assert {row["state"] for row in before} == {"accepted", "running"}

    request = start(composition, connect, authority, "withdraw")
    drive(composition.worker.lifecycle)

    with connect("research") as conn:
        after = {row["id"]: row for row in conn.execute(
            "SELECT id,state,error_code,fence FROM research.job WHERE id=ANY(%s)",
            (job_ids,)).fetchall()}
        kept = conn.execute("SELECT count(*) AS n FROM research.context WHERE owner_id=%s",
                            (authority.account_id,)).fetchone()["n"]
    assert {(row["state"], row["error_code"]) for row in after.values()} == {
        ("failed", "CANCELLED")}
    assert all(after[row["id"]]["fence"] > row["fence"] for row in before)
    assert kept >= 1  # withdrawal keeps the records
    with connect("topics") as conn:
        assert conn.execute("SELECT status FROM topics.followed_topic WHERE id=%s",
                            (topic["id"],)).fetchone()["status"] == "unsubscribed"
    assert export_flows.effect_row(connect, effect["id"])["state"] == "invalidated"
    state = scopes(connect, request)
    for participant in ("ResearchWorkspace", "TopicsDigests", "ApprovedExport"):
        assert all(row["disposition"] == "complete"
                   for (name, _), row in state.items() if name == participant)
    # A withdrawal needs no tombstone; the backups scope has evidence once a live set has
    # passed in this realm, and until then waits with no attempt spent past the first.
    assert state[("ServiceOperations", "restore_enforcement")]["reason_key"] == (
        "no-tombstone-needed")
    assert state[("ServiceOperations", "backups")]["attempts"] <= 1
    with connect("research") as conn:
        conn.execute("UPDATE research.job SET usage_state='released' WHERE id=ANY(%s)",
                     (job_ids,))


# --- 3. Reactivate serves again only what withdrawal kept --------------------------------


def seed_reactivation(connect, composition, account) -> str:
    """The reactivation request AccountAccess's `reactivate` writes after its proof."""
    from psycopg.types.json import Jsonb

    service = composition.parts["account-controls"]["lifecycle"]
    request, revision = uuid4(), uuid4()
    with connect("accounts") as conn:
        conn.execute(
            "INSERT INTO accounts.lifecycle_request(id,account_id,revision,action,policy_ref,"
            "manifest_revision,manifest,disposition,reason_key) VALUES(%s,%s,%s,'reactivate',"
            "%s,%s,%s,'pending','restoration-evidence-pending')",
            (request, account, revision, Jsonb(service.entry.control_policy.reference),
             service.revision, Jsonb(service.manifest)))
        for participant, scope in service.manifest:
            conn.execute("INSERT INTO accounts.lifecycle_scope(request_id,participant,scope) "
                         "VALUES(%s,%s,%s)", (request, participant, scope))
        conn.execute("UPDATE accounts.account SET lifecycle_revision=%s WHERE id=%s",
                     (revision, account))
    return str(request)


def test_reactivate_serves_again_only_what_withdrawal_kept(
    composition, connect, transactions, lifecycle_account,
):
    authority = lifecycle_account("lifecycle-reactivate")
    job_ids = research_work(transactions, authority)
    start(composition, connect, authority, "withdraw")
    drive(composition.worker.lifecycle)
    request = seed_reactivation(connect, composition, authority.account_id)
    drive(composition.worker.lifecycle)
    state = scopes(connect, request)
    research = {scope: row for (name, scope), row in state.items()
                if name == "ResearchWorkspace"}
    assert all(row["disposition"] == "complete" for row in research.values())
    assert state[("ServiceOperations", "restore_enforcement")]["reason_key"] == (
        "no-tombstone-needed")
    with connect("research") as conn:
        jobs = conn.execute("SELECT state FROM research.job WHERE id=ANY(%s)",
                            (job_ids,)).fetchall()
        contexts = conn.execute("SELECT count(*) AS n FROM research.context WHERE owner_id=%s",
                                (authority.account_id,)).fetchone()["n"]
        counts = conn.execute("SELECT action,scope FROM research.lifecycle_counts WHERE "
                              "request_id=%s", (request,)).fetchall()
        conn.execute("UPDATE research.job SET usage_state='released' WHERE id=ANY(%s)",
                     (job_ids,))
    assert {row["state"] for row in jobs} == {"failed"}  # stopped work stays stopped
    assert contexts >= 1  # the kept records are there to be served again
    assert {row["action"] for row in counts} == {"reactivate"}


# --- 4. An erase completes only with all 21 scopes' evidence --------------------------------


def record_backup_set(ledger, *, retain_until: str) -> dict:
    receipt = str(uuid4())
    record = {
        "backupId": str(uuid4()), "environment": "live", "revision": 1,
        "trigger": "scheduled", "takenAt": utc_text(ledger.clock()), "checksum": "b" * 64,
        "sizeBytes": 10, "sourceDatabaseBytes": 20, "location": "archives/live.dump",
        "databaseIncarnation": "cluster:docsuri_u8:1", "stagingLocation": "staging/live.dump",
        "stagingRemovedAt": utc_text(ledger.clock()), "retainUntil": retain_until,
        "integrity": "passed", "operatorReceiptRef": receipt,
    }
    ledger.append("backup-set", record, expect_revision=0, receipts=[{
        "receiptId": receipt, "operationId": str(uuid4()), "operation":
        "platform.database.backup", "targetId": "docsuri_u8", "inputHash": "c" * 64,
        "outcome": "succeeded", "confirmedAt": utc_text(ledger.clock())}])
    return record


def record_verification(ledger, head: dict, backup_id: str) -> dict:
    now = utc_text(ledger.clock())
    record = {
        "verificationId": str(uuid4()), "environment": "live", "backupId": backup_id,
        "startedAt": now, "finishedAt": now, "registerHeadSequence": head["sequence"],
        "registerHeadDigest": head["digest"], "integrity": "passed",
        "erasedOwnersSurviving": 0, "result": "verified",
        "evidenceRef": "evidence/verification.json", "scratchRemovedAt": now,
    }
    ledger.append("restore-verification", record, expect_revision=0)
    return record


def test_an_erase_completes_only_when_all_21_scopes_have_evidence(
    composition, connect, lifecycle_account,
):
    authority = lifecycle_account("lifecycle-erase")
    ledger = composition.parts["service-operations"]["ledger"]
    register = Tombstones(ledger)
    # The realm's ledger persists across phases: an earlier run may have left a live set.
    passed = any(item["environment"] == "live" and item["integrity"] == "passed"
                 for item in ledger.records("backup-set"))
    request = start(composition, connect, authority, "erase")
    drive(composition.worker.lifecycle)
    state = scopes(connect, request)
    assert len(state) == 21
    waiting = sorted(key for key, row in state.items() if row["disposition"] != "complete")
    assert waiting == ([] if passed else [("ServiceOperations", "backups")]) + [
        ("ServiceOperations", "restore_enforcement")]
    assert request_row(connect, request)["disposition"] != "complete"
    tombstone = register.by_request(request)
    assert tombstone["accountId"] == str(authority.account_id)
    # A verification that stops short of the tombstone gives no evidence.
    later = utc_text(ledger.clock() + dt.timedelta(days=14))
    backup = record_backup_set(ledger, retain_until=later)
    short = {"sequence": tombstone["sequence"] - 1,
             "digest": register.all()[tombstone["sequence"] - 2]["digest"]
             if tombstone["sequence"] > 1 else "0" * 64}
    record_verification(ledger, short, backup["backupId"])
    expire_leases(connect, request)
    drive(composition.worker.lifecycle)
    state = scopes(connect, request)
    assert state[("ServiceOperations", "backups")]["disposition"] == "complete"
    assert state[("ServiceOperations", "restore_enforcement")]["disposition"] != "complete"
    # The verification that covers it completes the erase.
    covering = record_verification(ledger, register.head(), backup["backupId"])
    expire_leases(connect, request)
    drive(composition.worker.lifecycle)
    state = scopes(connect, request)
    assert all(row["disposition"] == "complete" for row in state.values())
    assert all(row["attempts"] <= 2 for row in state.values())
    assert request_row(connect, request)["disposition"] == "complete"
    evidence = ledger.get("lifecycle-evidence", (request, "restore_enforcement"))
    assert evidence["verificationId"] == covering["verificationId"]
    assert evidence["registerHeadSequence"] >= tombstone["sequence"]
    # The covering verification's times (L1-42), and no late-start mark: it started
    # within `erasure_verification_start_seconds` of the tombstone.
    assert evidence["verificationStartedAt"] == covering["startedAt"]
    assert evidence["verificationFinishedAt"] == covering["finishedAt"]
    assert parse_time(covering["startedAt"]) - parse_time(tombstone["appendedAt"]) <= (
        dt.timedelta(seconds=composition.policy.erasure_verification_start_seconds))
    assert not evidence.get("verificationStartLate", False)
    backups = ledger.get("lifecycle-evidence", (request, "backups"))
    assert backups["setsCounted"] >= 1 and "latestGoneAt" in backups
    if not passed:  # the evidence was taken after this test's set was recorded
        assert backups["latestGoneAt"] >= later
        # It names this test's set by its id, with its date (Step 64(f)).
        assert {"recordId": backup["backupId"], "kind": "backup-set",
                "goneAt": later} in backups["undisposed"]


# --- 5. A request keeps its revision ----------------------------------------------------


def test_a_request_keeps_its_revision_when_the_manifest_changes(
    composition, connect, lifecycle_account,
):
    authority = lifecycle_account("lifecycle-revision")
    request = start(composition, connect, authority, "withdraw")
    controls = composition.parts["account-controls"]
    from backend.modules.accounts.u8_lifecycle import CompleteLifecycleService

    revised = CompleteLifecycleService(controls["entry"], LIFECYCLE_MANIFEST,
                                       revision="u8-owners-v2")
    worker = lifecycle_worker(composition, {**controls, "lifecycle": revised})
    drive(worker, passes=2)
    row = request_row(connect, request)
    assert row["manifest_revision"] == LIFECYCLE_REVISION
    assert all(item["attempts"] == 0 for item in scopes(connect, request).values())
    with pytest.raises(ValueError):
        revised.claim(request, "Library", "live_records")
    # Under its own revision it proceeds.
    drive(composition.worker.lifecycle, passes=1)
    assert any(item["disposition"] == "complete"
               for item in scopes(connect, request).values())


# --- 6. External copies are retained by policy ----------------------------------------------


def test_approved_exports_external_copies_are_reported_as_retained_by_policy(
    composition, connect, lifecycle_account,
):
    authority = lifecycle_account("lifecycle-copies")
    request = start(composition, connect, authority, "erase")
    drive(composition.worker.lifecycle)
    service = composition.parts["account-controls"]["lifecycle"]
    with connect("accounts") as conn:
        account = conn.execute("SELECT * FROM accounts.account WHERE id=%s",
                               (authority.account_id,)).fetchone()
        value = service._status(conn, request_row(connect, request), account)
    export = next(item for item in value["participants"]
                  if item["participantId"] == "ApprovedExport")
    by_scope = {item["scope"]: item for item in export["scopes"]}
    assert by_scope["external_copies"]["disposition"] == "retained_by_policy"
    assert by_scope["external_copies"]["reasonKey"] == "external-copies-retained-by-owner"
    assert by_scope["live_records"]["disposition"] == "erased"


# --- 7. Backups are retained by policy until their date (your decision of 2026-10-22) ------


def parse_time(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def composed_backups_evidence(composition) -> dict:
    """`backups_evidence` over the realm's ledger with the composition's policy and the
    readers the composition hands ServiceOperations' lifecycle participant."""
    from backend.modules.operations.lifecycle import backups_evidence
    from backend.u8_host import backup_schedule_active

    platform = composition.parts.get("platform-control") or {}
    inspect = platform.get("inspect")
    return backups_evidence(
        composition.parts["service-operations"]["ledger"], composition.policy,
        schedule_active=backup_schedule_active(composition.profile),
        open_operations=None if inspect is None else inspect.open_operations,
        agent_status=platform.get("evidence_reader"),
        status_required=composition.profile.is_production)


def test_an_erased_owner_with_an_undisposed_backup_set_sees_backups_retained_until_its_date(
    composition, connect, lifecycle_account,
):
    from backend.modules.operations.lifecycle import EvidencePending

    authority = lifecycle_account("lifecycle-backups")
    ledger = composition.parts["service-operations"]["ledger"]
    # The seeded set's date falls after every date the realm's ledger already holds (Step
    # 90(d)): the prior evidence's latest date + 1 day, or now + 30 days if that is later.
    target = ledger.clock() + dt.timedelta(days=30)
    try:
        prior = composed_backups_evidence(composition).get("latestGoneAt")
    except EvidencePending:
        prior = None
    if prior is not None:
        target = max(target, parse_time(prior) + dt.timedelta(days=1))
    later = utc_text(target)
    record_backup_set(ledger, retain_until=later)  # a live set that passed, undisposed
    request = start(composition, connect, authority, "erase")
    drive(composition.worker.lifecycle)
    state = scopes(connect, request)
    backups = state[("ServiceOperations", "backups")]
    assert (backups["disposition"], backups["reason_key"]) == (
        "complete", "backups-retained-until-disposal")
    evidence = ledger.get("lifecycle-evidence", (request, "backups"))
    # The erase's evidence is `backups_evidence` over the same ledger under the
    # composition's policy, and its latest date is exactly the seeded set's.
    expected = composed_backups_evidence(composition)
    assert {name: evidence.get(name) for name in expected} == expected
    assert evidence["latestGoneAt"] == later
    # The date is kept beside the scope's evidence, and the status shows it.
    with connect("accounts") as conn:
        stored = conn.execute(
            "SELECT retained_until FROM accounts.lifecycle_scope WHERE request_id=%s AND "
            "participant='ServiceOperations' AND scope='backups'", (request,),
        ).fetchone()["retained_until"]
        unrelated = conn.execute(
            "SELECT count(*) AS n FROM accounts.lifecycle_scope WHERE request_id=%s AND "
            "retained_until IS NOT NULL", (request,),
        ).fetchone()["n"]
        account = conn.execute("SELECT * FROM accounts.account WHERE id=%s",
                               (authority.account_id,)).fetchone()
        service = composition.parts["account-controls"]["lifecycle"]
        value = service._status(conn, request_row(connect, request), account)
    assert stored == parse_time(evidence["latestGoneAt"]) == parse_time(later)
    assert unrelated == 1
    operations = next(item for item in value["participants"]
                      if item["participantId"] == "ServiceOperations")
    part = {item["scope"]: item for item in operations["scopes"]}["backups"]
    assert part["disposition"] == "retained_by_policy"
    assert part["reasonKey"] == "backups-retained-until-disposal"
    assert parse_time(part["retainedUntil"]) == stored
    # Every other part of the erase reports no date.
    assert all("retainedUntil" not in scope
               for item in value["participants"] for scope in item["scopes"]
               if (item["participantId"], scope["scope"]) != ("ServiceOperations", "backups"))
    # Step 44's correction: a replayed acknowledgement keeps the stored date, and a replay
    # never adds one to a part that has none.
    for participant, scope in (("ServiceOperations", "backups"),
                               ("ApprovedExport", "external_copies")):
        ticket, row = completed_ticket(connect, request, participant, scope)
        service.acknowledge(ticket, evidence=row["evidence_ref"], reason=row["reason_key"],
                            retained_until=stored + dt.timedelta(days=10))
    with connect("accounts") as conn:
        dates = {row["part"]: row["retained_until"] for row in conn.execute(
            "SELECT participant||':'||scope AS part,retained_until FROM "
            "accounts.lifecycle_scope WHERE request_id=%s AND retained_until IS NOT NULL",
            (request,),
        ).fetchall()}
    assert dates == {"ServiceOperations:backups": stored}


def completed_ticket(connect, request, participant: str, scope: str) -> tuple[dict, dict]:
    """A completed scope's ticket as its claim left it, for a replayed acknowledgement."""
    with connect("accounts") as conn:
        row = conn.execute(
            "SELECT * FROM accounts.lifecycle_scope WHERE request_id=%s AND participant=%s "
            "AND scope=%s", (request, participant, scope)).fetchone()
        owner = conn.execute("SELECT * FROM accounts.lifecycle_request WHERE id=%s",
                             (request,)).fetchone()
    assert row["disposition"] == "complete"
    ticket = dict(row, account_id=owner["account_id"], lifecycle_revision=owner["revision"],
                  action=owner["action"], policy_ref=owner["policy_ref"],
                  manifest_revision=owner["manifest_revision"])
    return ticket, row


# --- 8. A participant's date reaches AccountAccess as an aware time ----------------------


class TextDates:
    """ServiceOperations' participant, reporting its retention date as `render` makes it
    (an ISO string, as a participant across a boundary may)."""

    def __init__(self, participant, render):
        self._participant, self._render = participant, render

    def __getattr__(self, name):
        return getattr(self._participant, name)

    def apply(self, ticket):
        result = dict(self._participant.apply(ticket))
        if result.get("retainedUntil") is not None:
            result["retainedUntil"] = self._render(result["retainedUntil"])
        return result


@pytest.mark.parametrize(("render", "accepted"), [
    # One account each (the realm's account budget): an ISO string with its offset, and
    # one without; `test_retention_date.py` covers every other form directly.
    (lambda moment: moment.isoformat().replace("+00:00", "Z"), True),
    (lambda moment: moment.replace(tzinfo=None).isoformat(), False),
])
def test_a_participants_iso_date_is_parsed_and_a_naive_or_malformed_one_refused(
    composition, connect, lifecycle_account, monkeypatch, render, accepted,
):
    # Two of this module's accounts again (the realm's account budget); each is reset.
    authority = lifecycle_account("lifecycle-backups" if accepted else "lifecycle-copies")
    ledger = composition.parts["service-operations"]["ledger"]
    record_backup_set(ledger, retain_until=utc_text(ledger.clock() + dt.timedelta(days=30)))
    worker = composition.worker.lifecycle
    monkeypatch.setitem(worker.participants, "ServiceOperations",
                        TextDates(worker.participants["ServiceOperations"], render))
    request = start(composition, connect, authority, "erase")
    drive(worker)  # never raises, whatever the participant reported
    backups = scopes(connect, request)[("ServiceOperations", "backups")]
    with connect("accounts") as conn:
        stored = conn.execute(
            "SELECT retained_until FROM accounts.lifecycle_scope WHERE request_id=%s AND "
            "participant='ServiceOperations' AND scope='backups'", (request,),
        ).fetchone()["retained_until"]
    if accepted:
        evidence = ledger.get("lifecycle-evidence", (request, "backups"))
        assert backups["disposition"] == "complete"
        assert stored is not None and stored.tzinfo is not None
        assert stored == parse_time(evidence["latestGoneAt"])
    else:
        assert backups["disposition"] != "complete" and stored is None
        assert backups["reason_key"] == "retention-date-invalid"
