"""UsageEntitlements in the two complete realms (U8 plan Steps 24 and 31; the person's
decisions of 2026-10-23, "U2's controls for all usage" and "Grant migrated accounts",
and of 2026-10-24, "Move, scope tools, test U2").

- `ResearchUsageService` is U2's `ControlUsageService` for ResearchWorkspace's research
  and novelty reservations, counted in the same policy period as paper assistance and
  recorded with `ResearchWorkspace` as their owner.
- `ImportedUsage` is UsageEntitlements' `grantImportedUsage` and its parity read, for
  the migration's import and the composed realm's fixtures, under trusted composition
  authority. It refuses U2's realm and policy.
- `CompleteUsage` gives research and paper assistance the built usage repository's
  interface over U2's controls under the realm's policy. An account holds usage only
  once an administrator or the migration grants it, so nothing is allocated here.
- `use_complete_usage(part, transactions)` gives a built part (ResearchWorkspace's
  execution, PaperAssistance's dispatch) `CompleteUsage`, and its admission too; the
  composition check refuses a start where any usage authority is not `CompleteUsage`.

U2's realm keeps U2's built usage controls, and every earlier realm its built path.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from psycopg.types.json import Jsonb

from backend.modules.accounts.control_policy import PolicyUnavailable
from backend.modules.plans.control_service import ControlUsageService
from backend.modules.plans.guarded_repository import GuardedUsageRepository
from backend.modules.summarization.guarded_repository import intent_digest
from backend.transactions import Authority

COMPLETE_REALMS = ("service-operations", "production")
# The trusted composition actor the migration's grants are receipted under (no account).
IMPORT_ACTOR = uuid5(NAMESPACE_URL, "docsuri-migration-import:usage")
MAX_PARITY_RECORDS = 100_000


def _complete_policy(transactions, policy):
    from backend.modules.accounts.u8_control_policy import CompletePolicy

    if transactions.profile.realm not in COMPLETE_REALMS or not isinstance(
        policy, CompletePolicy
    ):
        raise PolicyUnavailable("complete usage runs only in a complete realm, under its policy")
    return policy


class ResearchUsageService(ControlUsageService):
    """U2's usage controls for ResearchWorkspace's reservations."""

    operation_owner = "ResearchWorkspace"

    def __init__(self, transactions, policy):
        super().__init__(transactions, _complete_policy(transactions, policy))

    def current_period(self) -> str:
        return self.transactions.run("usage", self._period)

    def reserve_operation(self, authority: Authority, operation: UUID,
                          intent_hash: str) -> dict:
        """A research or novelty reservation under the realm's policy, counted in the
        same period as paper assistance."""
        admission = {
            "account_id": authority.account_id, "disposition": "open", "quantity": 1,
            "policy_ref": self.policy.reference, "operation_id": operation,
            "intent_hash": intent_hash, "generation": 1, "period_id": self.current_period(),
        }
        return self.reserve(authority, admission)


class ImportedUsage(ControlUsageService):
    """`grantImportedUsage` and the owner's parity read of the grants (Step 31)."""

    def __init__(self, transactions, policy):
        super().__init__(transactions, _complete_policy(transactions, policy))

    def grant_fields(self, target: UUID) -> dict:
        """The normalized fields an imported account's grant stores: the policy's full
        quota under the realm's own policy, not revoked."""
        return {"account": str(target), "allocation": self.policy.quota,
                "policy": self.policy.policy_id, "revoked": False}

    def grant_imported(self, target: UUID, *, source: str = "migration_import") -> dict:
        """`grantImportedUsage`: an imported account that is active in v2 gets its usage
        under the realm's own policy, through the same grant the administrator's routes
        write, under trusted composition authority (the migration tool's import, never a
        browser route). A closed or not-active account gets none (`account-not-active`);
        an account that already holds an entitlement is left as it is (`unchanged` when
        it is this grant, refused `entitlement-differs` otherwise), so the idempotency
        pass grants nothing new. Answers A4's `ImportOutcome`. `source` names who granted
        it in the receipt: the migration's import, or the composed realm's fixtures."""
        if source not in ("migration_import", "realm_fixture"):
            raise ValueError("grant source outside its vocabulary")
        from backend.import_parity import outcome, stored_digest

        fields = self.grant_fields(target)
        digest = stored_digest(fields)
        intent = intent_digest({"imported": str(target), "policy": self.policy.policy_id})

        def write(conn):
            if not conn.execute(
                "SELECT accounts.assignment_target_available(%s) AS allowed", (target,)
            ).fetchone()["allowed"]:
                return outcome("refused", digest, reason="account-not-active")
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,24))", (str(target),))
            row = conn.execute(
                "SELECT * FROM usage.entitlement WHERE account_id=%s FOR UPDATE", (target,)
            ).fetchone()
            if row is not None:
                same = stored_digest({"account": str(row["account_id"]),
                                      "allocation": row["allocation"],
                                      "policy": row["policy"],
                                      "revoked": row["revoked"]}) == digest
                return (outcome("unchanged", digest) if same
                        else outcome("refused", digest, reason="entitlement-differs"))
            revision = uuid4()
            # One receipt per grant: the entitlement is what makes the grant idempotent.
            operation = uuid5(NAMESPACE_URL, f"docsuri-imported-usage:{target}:{revision}")
            assigned = conn.execute(
                "INSERT INTO usage.entitlement(account_id,allocation,policy,revoked,"
                "assignment_revision,period_id) VALUES(%s,%s,%s,false,%s,%s) "
                "RETURNING created_at",
                (target, self.policy.quota, self.policy.policy_id, revision, self._period(conn)),
            ).fetchone()
            conn.execute(
                "INSERT INTO usage.assignment_receipt(actor_id,key,target_id,intent_hash,outcome) "
                "VALUES(%s,%s,%s,%s,%s)",
                (IMPORT_ACTOR, operation, target, intent, Jsonb({
                    "entitlementId": str(target), "accountId": str(target),
                    "tierId": "synthetic-free", "assignmentSource": source,
                    "policyRef": self.policy.reference,
                    "effectiveAt": assigned["created_at"].isoformat(),
                    "disposition": "active", "revision": str(revision)})),
            )
            return outcome("imported", digest)

        return self.transactions.run("usage", write)

    def imported_parity(self, *, now: datetime) -> dict:
        """The owner's parity read of the grants: every entitlement under the realm's own
        policy, as `grant_fields` digests them."""
        from backend.import_parity import parity, stored_digest

        def read(conn):
            return conn.execute(
                "SELECT account_id,allocation,policy,revoked FROM usage.entitlement "
                "WHERE policy=%s ORDER BY account_id LIMIT %s",
                (self.policy.policy_id, MAX_PARITY_RECORDS + 1),
            ).fetchall()

        rows = self.transactions.run("usage", read)
        if len(rows) > MAX_PARITY_RECORDS:
            raise ValueError("parity read exceeds its bound")
        observed = now.astimezone(UTC).isoformat(timespec="microseconds").replace(
            "+00:00", "Z")
        return parity("usage-grant", [stored_digest({
            "account": str(row["account_id"]), "allocation": row["allocation"],
            "policy": row["policy"], "revoked": row["revoked"]}) for row in rows], observed)


class CompleteUsage:
    """Every usage call of the two complete realms through U2's controls under the
    realm's policy, with `GuardedUsageRepository`'s interface so research, novelty and
    paper assistance keep their calls: a reservation is U2's, counted per policy period
    with paper assistance; settlement, release and the refusal clean-up are the same
    ledger rows U2's records show; and an account holds usage only once granted, so
    nothing is allocated here."""

    def __init__(self, transactions, policy):
        self.transactions = transactions
        self.control = ResearchUsageService(transactions, policy)
        self.repository = GuardedUsageRepository(transactions)

    def ensure_entitlement(self, authority: Authority) -> None:
        """U2's rule: no usage until an administrator or the migration grants it."""
        return None

    def reserve(self, authority: Authority, operation: UUID, intent_hash: str) -> dict:
        return self.control.reserve_operation(authority, operation, intent_hash)

    def reject_operation(self, proof: dict) -> None:
        self.repository.reject_operation(proof)

    def settle(self, reservation: UUID, operation: UUID, *, disposition: str,
               proof_hash: str) -> dict:
        return self.repository.settle(reservation, operation, disposition=disposition,
                                      proof_hash=proof_hash)

    def reservation(self, authority: Authority, operation: UUID) -> dict | None:
        return self.repository.reservation(authority, operation)

    def current(self, authority: Authority) -> dict:
        return self.repository.current(authority)


def usage_for(transactions):
    """The usage authority of a realm: `CompleteUsage` in the two complete realms, the
    built repository everywhere else."""
    from backend.modules.accounts.control_policy import for_realm

    if transactions.profile.realm in COMPLETE_REALMS:
        return CompleteUsage(transactions, for_realm(transactions.profile.realm))
    return GuardedUsageRepository(transactions)


def use_complete_usage(part, transactions):
    """Give a built part (ResearchWorkspace's execution, PaperAssistance's dispatch) the
    complete realms' usage authority, on the part and on its admission when that holds
    one. Refused outside the two complete realms."""
    if transactions.profile.realm not in COMPLETE_REALMS:
        raise PolicyUnavailable("complete usage runs only in the two complete realms")
    usage = usage_for(transactions)
    part.usage = usage
    admission = getattr(part, "admission", None)
    if admission is not None and hasattr(admission, "usage"):
        admission.usage = usage
    return part
