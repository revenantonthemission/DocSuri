"""Bounded current-owner cleanup; missing restore evidence never means completion."""

from __future__ import annotations

from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from backend.artifacts import ARTIFACT_IDENTITY
from backend.lifecycle_effects import apply_owner_effect
from backend.modules.library.control_lifecycle import LibraryLifecycleParticipant
from backend.modules.personalization.control_lifecycle import PersonalizationLifecycleParticipant
from backend.modules.plans.guarded_repository import GuardedUsageRepository
from backend.modules.summarization.admission import AssistanceAdmission
from backend.modules.summarization.guarded_repository import GuardedAssistanceRepository


class PendingLifecycleEvidence(RuntimeError):
    """A finite owner pass has more responsibility to reconcile."""


def purge(conn, owner, ticket):
    # Owner comes only from these installed classes, never browser input.
    from psycopg import sql

    conn.execute(
        sql.SQL("SELECT {}.erase_private_controls(%s,%s,%s,%s,%s)").format(sql.Identifier(owner)),
        (
            ticket["request_id"],
            ticket["account_id"],
            ticket["generation"],
            Jsonb(ticket["policy_ref"]),
            ticket["manifest_revision"],
        ),
    )


class AccountLifecycleParticipant:
    scopes = ("derived_artifacts", "live_records")

    def __init__(self, entry):
        self.entry, self.transactions = entry, entry.transactions

    def apply(self, ticket):
        def effect(conn, action, bound):
            if action != "erase":
                return
            if bound["scope"] == "live_records":
                purge(conn, "accounts", bound)
                return
            rows = conn.execute(
                "SELECT private_path FROM accounts.delivery WHERE challenge_id IN "
                "(SELECT id FROM accounts.challenge WHERE account_id=%s) LIMIT 101",
                (bound["account_id"],),
            ).fetchall()
            proofs = conn.execute(
                "SELECT id,protected_payload FROM accounts.control_proof "
                "WHERE account_id=%s AND purpose<>'reauthenticate' LIMIT 101",
                (bound["account_id"],),
            ).fetchall()
            if len(rows) > 100 or len(proofs) > 100:
                raise PendingLifecycleEvidence("mail-cleanup-bound-exceeded")
            names = {row["private_path"] for row in rows}
            for proof in proofs:
                payload = self.entry.reveal("proof:" + str(proof["id"]), proof["protected_payload"])
                if payload.get("delivery"):
                    names.add(payload["delivery"])
            for name in sorted(names):
                # The artifact store can only create, read or erase its own finite
                # identity form, so a stored name it cannot own references no private
                # bytes; an uninterpretable marker must not crash the bounded pass.
                if ARTIFACT_IDENTITY.fullmatch(str(name)):
                    self.entry.mail.erase(name)

        return apply_owner_effect(self.transactions, "accounts", self.scopes, ticket, effect)


class UsageLifecycleParticipant:
    scopes = ("live_records",)

    def __init__(self, transactions):
        self.transactions = transactions

    def apply(self, ticket):
        def effect(conn, action, bound):
            if action == "reactivate":
                # An explicit later administrator grant controls capacity; restore never grants it.
                return
            conn.execute(
                "UPDATE usage.entitlement SET revoked=true,assignment_revision=gen_random_uuid() "
                "WHERE account_id=%s",
                (bound["account_id"],),
            )
            if conn.execute(
                "SELECT 1 FROM usage.reservation "
                "WHERE account_id=%s AND disposition='reserved' LIMIT 1",
                (bound["account_id"],),
            ).fetchone():
                raise PendingLifecycleEvidence("accepted-accounting-responsibility-remains")

        result = apply_owner_effect(self.transactions, "usage", self.scopes, ticket, effect)
        result["reasonKey"] = "bounded-audit-identifiers-retained"
        return result


class DiscoveryLifecycleParticipant:
    scopes = ("live_records",)

    def __init__(self, transactions):
        self.transactions = transactions

    def apply(self, ticket):
        def effect(conn, action, bound):
            if action == "erase":
                purge(conn, "discovery", bound)
            elif action == "withdraw":
                conn.execute(
                    "UPDATE discovery.execution SET relay_state='suppressed' "
                    "WHERE account_id=%s AND relay_state='pending'",
                    (bound["account_id"],),
                )

        return apply_owner_effect(self.transactions, "discovery", self.scopes, ticket, effect)


class AssistanceLifecycleParticipant:
    scopes = ("derived_artifacts", "live_records", "pending_work")

    def __init__(self, transactions, files):
        self.transactions, self.files = transactions, files

    def apply(self, ticket):
        def effect(conn, action, bound):
            account = bound["account_id"]
            outstanding = conn.execute(
                "SELECT 1 FROM assistance.job WHERE account_id=%s "
                "AND (state IN ('accepted','running') OR settlement_pending) LIMIT 1",
                (account,),
            ).fetchone()
            open_admission = conn.execute(
                "SELECT 1 FROM assistance.admission "
                "WHERE account_id=%s AND disposition='open' LIMIT 1",
                (account,),
            ).fetchone()
            if outstanding or open_admission:
                raise PendingLifecycleEvidence("accepted-work-reconciliation-pending")
            if action == "reactivate" or bound["scope"] == "pending_work":
                return
            if action == "withdraw":
                conn.execute(
                    "UPDATE assistance.result SET availability='restricted' WHERE account_id=%s",
                    (account,),
                )
            elif bound["scope"] == "derived_artifacts":
                rows = conn.execute(
                    "SELECT private_path FROM assistance.result WHERE account_id=%s LIMIT 101",
                    (account,),
                ).fetchall()
                if len(rows) > 100:
                    raise PendingLifecycleEvidence("private-result-cleanup-bound-exceeded")
                for row in rows:
                    self.files.erase(row["private_path"])
            else:
                purge(conn, "assistance", bound)

        return apply_owner_effect(self.transactions, "assistance", self.scopes, ticket, effect)


class ControlWorker:
    """One finite pass, reusable after process restart; never a public command."""

    def __init__(self, entry, lifecycle, personalization, files):
        self.entry, self.transactions, self.lifecycle = entry, entry.transactions, lifecycle
        self.personalization = personalization
        self.participants = {
            "AccountAccess": AccountLifecycleParticipant(entry),
            "Library": LibraryLifecycleParticipant(self.transactions),
            "Personalization": PersonalizationLifecycleParticipant(self.transactions),
            "UsageEntitlements": UsageLifecycleParticipant(self.transactions),
            "DiscoveryCitations": DiscoveryLifecycleParticipant(self.transactions),
            "PaperAssistance": AssistanceLifecycleParticipant(self.transactions, files),
        }
        self.admission = AssistanceAdmission(
            GuardedAssistanceRepository(self.transactions, files),
            GuardedUsageRepository(self.transactions),
        )

    def apply_research_consent(self, fact):
        def write(conn):
            current = conn.execute(
                "SELECT * FROM accounts.assistance_effect_authority(%s)",
                (fact["account_id"],),
            ).fetchone()
            prior = conn.execute(
                "SELECT * FROM assistance.consent_evidence WHERE obligation_id=%s",
                (fact["id"],),
            ).fetchone()
            if prior:
                if (
                    prior["account_id"],
                    prior["consent_revision"],
                    prior["authority_revision"],
                ) != (fact["account_id"], fact["consent_revision"], fact["authority_revision"]):
                    raise ValueError("consent evidence binding conflict")
                return prior["evidence_ref"]
            disposition = "superseded"
            if (current["authority_revision"], current["consent_revision"], current["granted"]) == (
                fact["authority_revision"],
                fact["consent_revision"],
                fact["granted"],
            ):
                disposition = "applied"
                if not fact["granted"]:
                    if conn.execute(
                        "SELECT 1 FROM assistance.job WHERE account_id=%s "
                        "AND (state IN ('accepted','running') OR settlement_pending) LIMIT 1",
                        (fact["account_id"],),
                    ).fetchone():
                        raise PendingLifecycleEvidence("consent-work-reconciliation-pending")
                    conn.execute(
                        "UPDATE assistance.result SET availability='restricted' "
                        "WHERE account_id=%s",
                        (fact["account_id"],),
                    )
            evidence = uuid4()
            conn.execute(
                "INSERT INTO assistance.consent_evidence VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    fact["id"],
                    fact["account_id"],
                    fact["consent_revision"],
                    fact["authority_revision"],
                    evidence,
                    disposition,
                ),
            )
            return evidence

        return self.transactions.run("assistance", write)

    def run_once(self, limit=4):
        if type(limit) is not int or not 1 <= limit <= 4:
            raise ValueError("finite control-worker bound required")
        self.admission.reconcile_admissions(limit=limit)
        self.admission.recover_execution(limit=limit)
        from backend.modules.accounts.control_repository import ControlRepository

        repository = ControlRepository(self.transactions, self.entry.control_policy)
        for purpose in ("personalization", "local-research"):
            for fact in repository.pending_consents(limit=limit, purpose=purpose):
                try:
                    evidence = (
                        UUID(self.personalization.apply_consent_boundary(fact)["evidenceRef"])
                        if purpose == "personalization"
                        else self.apply_research_consent(fact)
                    )
                except PendingLifecycleEvidence:
                    continue
                repository.acknowledge_consent(fact["id"], fact["consent_revision"], evidence)
        resets = self.transactions.run(
            "personalization",
            lambda conn: conn.execute(
                "SELECT r.id FROM personalization.reset_responsibility r "
                "JOIN personalization.reset_scope s ON s.reset_id=r.id "
                "WHERE s.participant='Personalization' AND s.scope='behavior' "
                "AND s.disposition<>'complete' AND s.attempts<3 "
                "AND (s.lease_until IS NULL OR s.lease_until<=clock_timestamp()) "
                "ORDER BY r.accepted_at,r.id LIMIT %s",
                (limit,),
            ).fetchall(),
        )
        for row in resets:
            self.personalization.clean_reset(row["id"])
        requests = self.transactions.run(
            "accounts",
            lambda conn: conn.execute(
                "SELECT r.id FROM accounts.lifecycle_request r "
                "JOIN accounts.account a ON a.id=r.account_id "
                "WHERE r.revision=a.lifecycle_revision AND r.disposition<>'complete' "
                "AND r.manifest_revision=%s AND EXISTS (SELECT 1 FROM accounts.lifecycle_scope s "
                "WHERE s.request_id=r.id AND s.disposition<>'complete' AND s.attempts<3 "
                "AND (s.lease_until IS NULL OR s.lease_until<=clock_timestamp())) "
                "ORDER BY r.accepted_at,r.id LIMIT %s",
                (self.lifecycle.revision, limit),
            ).fetchall(),
        )
        outcomes = []
        for request in requests:
            for participant, scope in self.lifecycle.manifest:
                try:
                    ticket = self.lifecycle.claim(request["id"], participant, scope)
                except ValueError:
                    continue  # complete, leased, superseded or exhausted remains recorded
                adapter = self.participants.get(participant)
                if adapter is None or scope not in adapter.scopes:
                    self.lifecycle.acknowledge(
                        ticket, evidence=None, reason="required-scope-evidence-unavailable"
                    )
                    continue
                try:
                    result = adapter.apply(ticket)
                except PendingLifecycleEvidence as error:
                    self.lifecycle.acknowledge(ticket, evidence=None, reason=str(error))
                    continue
                outcomes.append(
                    self.lifecycle.acknowledge(
                        ticket, evidence=UUID(result["evidenceRef"]), reason=result["reasonKey"]
                    )
                )
        return {"requestsInspected": len(requests), "scopesAcknowledged": len(outcomes)}
