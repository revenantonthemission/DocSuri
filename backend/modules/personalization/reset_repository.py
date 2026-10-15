"""Reset acceptance and independently advancing owner responsibility projection."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from docsuri_shared.workspace import wire
from psycopg.types.json import Jsonb

from backend.modules.accounts.control_cursor import ControlCursor
from backend.modules.accounts.control_policy import ControlPolicy
from backend.modules.personalization.guarded_service import GuardedSettingsService
from backend.modules.summarization.guarded_repository import intent_digest
from backend.transactions import Authority, OwnerTransactions, guard


class ResetRepository:
    def __init__(
        self, transactions: OwnerTransactions, policy: ControlPolicy, cursor: ControlCursor
    ):
        policy.require_realm(transactions.profile.realm)
        self.transactions, self.policy, self.cursor = transactions, policy, cursor

    @staticmethod
    def summary(row: dict, observed: datetime) -> dict:
        return {
            "resetId": str(row["id"]),
            "action": row["action"],
            "acceptedAt": row["accepted_at"].isoformat(),
            "acceptedSettingsRevision": str(row["accepted_settings_revision"]),
            "inputBoundary": str(row["input_boundary"]),
            "policyRef": row["policy_ref"],
            "manifestRevision": row["manifest_revision"],
            "statusRevision": str(row["status_revision"]),
            "observedAt": observed.isoformat(),
            "disposition": row["disposition"],
            "reasonKey": row["reason_key"],
        }

    def inspect(self, authority: Authority, identifier: UUID) -> dict:
        def read(conn):
            guard(conn, authority, purpose="account-control")
            row = conn.execute(
                "SELECT *,clock_timestamp() AS observed FROM personalization.reset_responsibility "
                "WHERE id=%s AND account_id=%s",
                (identifier, authority.account_id),
            ).fetchone()
            if row is None:
                raise PermissionError("reset unavailable")
            scopes = conn.execute(
                "SELECT * FROM personalization.reset_scope WHERE reset_id=%s "
                "ORDER BY participant,scope LIMIT %s",
                (identifier, self.policy.max_scopes + 1),
            ).fetchall()
            if not scopes or len(scopes) > self.policy.max_scopes:
                raise RuntimeError("reset manifest incomplete")
            value = {
                "reset": self.summary(row, row["observed"]),
                "scopes": [
                    {
                        "participantId": item["participant"],
                        "scopeId": item["scope"],
                        "manifestRevision": item["manifest_revision"],
                        "workGeneration": str(item["generation"]),
                        "disposition": item["disposition"],
                        "reasonKey": item["reason_key"],
                        "evidenceRef": str(item["evidence_ref"]) if item["evidence_ref"] else None,
                        "updatedAt": item["updated_at"].isoformat(),
                    }
                    for item in scopes
                ],
            }
            return wire.SettingsResetStatus.model_validate(value).model_dump(mode="json")

        return self.transactions.run("personalization", read)

    def list(
        self, authority: Authority, *, view: str, limit: int, cursor: str | None = None
    ) -> dict:
        if (
            view not in ("outstanding", "history")
            or type(limit) is not int
            or not 1 <= limit <= self.policy.max_page_size
        ):
            raise ValueError("invalid reset page")
        def read(conn):
            revision = guard(conn, authority, purpose="account-control")
            scope = ":".join(("reset", view, self.policy.policy_id, str(limit), str(revision)))
            position = self.cursor.decode(authority.account_id, scope, cursor) if cursor else None
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            cutoff = datetime.fromisoformat(position["cutoff"]) if position else now
            # A cutoff freezes membership against subsequently accepted resets.
            rows = conn.execute(
                "SELECT * FROM personalization.reset_responsibility WHERE account_id=%s "
                "AND accepted_at<=%s AND (%s='history' OR disposition<>'complete') "
                "AND (%s::timestamptz IS NULL OR (accepted_at,id)<(%s::timestamptz,%s::uuid)) "
                "ORDER BY accepted_at DESC,id DESC LIMIT %s",
                (
                    authority.account_id,
                    cutoff,
                    view,
                    position["time"] if position else None,
                    position["time"] if position else None,
                    position["id"] if position else None,
                    limit + 1,
                ),
            ).fetchall()
            more = len(rows) > limit
            items = rows[:limit]
            next_cursor = (
                self.cursor.encode(
                    authority.account_id,
                    scope,
                    {
                        "cutoff": cutoff.isoformat(),
                        "time": items[-1]["accepted_at"].isoformat(),
                        "id": str(items[-1]["id"]),
                    },
                )
                if more
                else None
            )
            value = {
                "items": [self.summary(item, now) for item in items],
                "page": {"nextCursor": next_cursor, "snapshotRevision": cutoff.isoformat()},
                "appliedLimit": limit,
                "policyRef": self.policy.reference,
            }
            return wire.SettingsResetPage.model_validate(value).model_dump(mode="json")

        return self.transactions.run("personalization", read)

    def accept(
        self,
        authority: Authority,
        operation: UUID,
        expected: UUID,
        action: str,
        *,
        manifest: tuple[tuple[str, str], ...],
        manifest_revision: str,
        confirmation: UUID | None = None,
    ) -> dict:
        if (
            action not in ("delete_behavior", "reset_profile")
            or not manifest
            or len(manifest) > self.policy.max_scopes
            or len(set(manifest)) != len(manifest)
        ):
            raise ValueError("complete bounded reset manifest required")
        fingerprint = intent_digest(
            {
                "action": action,
                "expectedRevision": str(expected),
                "manifest": manifest,
                "manifestRevision": manifest_revision,
                "policy": self.policy.reference,
                "confirmation": str(confirmation) if confirmation else None,
            }
        )

        def write(conn):
            guard(conn, authority, purpose="account-control")
            consent_revision = conn.execute(
                "SELECT accounts.personalization_consent_revision(%s,%s) AS revision",
                (authority.account_id, authority.session_id),
            ).fetchone()["revision"]
            # Owner-local advisory lock serializes absent settings plus receipt keys.
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,22))",
                (str(authority.account_id),),
            )
            prior = conn.execute(
                "SELECT * FROM personalization.receipt WHERE account_id=%s AND kind='reset' AND key=%s",
                (authority.account_id, operation),
            ).fetchone()
            if prior:
                if prior["intent_hash"] != fingerprint:
                    raise ValueError("reset operation conflict")
                return prior["outcome"]
            row = conn.execute(
                "SELECT * FROM personalization.settings WHERE account_id=%s FOR UPDATE",
                (authority.account_id,),
            ).fetchone()
            previous = GuardedSettingsService._snapshot(authority.account_id, row)
            if previous["revision"] != str(expected):
                raise ValueError("stale settings revision")
            if confirmation is not None:
                conn.execute(
                    "SELECT accounts.consume_reset_confirmation(%s,%s,%s,%s,%s,%s,%s)",
                    (confirmation, authority.account_id, authority.session_id, action, expected,
                     Jsonb(self.policy.reference), operation),
                )
            count = conn.execute(
                "SELECT count(*) AS n FROM personalization.reset_responsibility WHERE account_id=%s AND disposition<>'complete'",
                (authority.account_id,),
            ).fetchone()["n"]
            if count >= self.policy.max_outstanding:
                raise ValueError("finite outstanding reset limit")
            boundary = (row["input_boundary"] if row else 0) + 1
            revision, identifier = uuid4(), uuid4()
            defaults = dict(row["defaults"]) if row else {}
            if action == "reset_profile":
                defaults.pop("interestIds", None)
                defaults["onboarding"] = "not_started"
            conn.execute(
                "INSERT INTO personalization.settings(account_id,revision,defaults,input_boundary) VALUES(%s,%s,%s,%s) "
                "ON CONFLICT(account_id) DO UPDATE SET revision=excluded.revision,defaults=excluded.defaults,input_boundary=excluded.input_boundary",
                (authority.account_id, revision, Jsonb(defaults), boundary),
            )
            accepted = conn.execute(
                "INSERT INTO personalization.reset_responsibility(id,account_id,action,accepted_settings_revision,"
                "input_boundary,policy_ref,manifest_revision,disposition,reason_key) VALUES(%s,%s,%s,%s,%s,%s,%s,'pending','cleanup-pending') RETURNING *",
                (
                    identifier,
                    authority.account_id,
                    action,
                    revision,
                    boundary,
                    Jsonb(self.policy.reference),
                    manifest_revision,
                ),
            ).fetchone()
            for participant, scope in sorted(manifest):
                conn.execute(
                    "INSERT INTO personalization.reset_scope(reset_id,participant,scope,manifest_revision) VALUES(%s,%s,%s,%s)",
                    (identifier, participant, scope, manifest_revision),
                )
            outcome = wire.SettingsResetResult.model_validate(
                {
                    "resetId": str(identifier),
                    "ack": {
                        "resourceId": str(identifier),
                        "revision": str(revision),
                        "requestId": str(operation),
                    },
                    "inputBoundary": str(boundary),
                    "consentRevision": str(consent_revision),
                    "disposition": "pending",
                    "remainingScopeReasonKey": "cleanup-pending",
                }
            ).model_dump(mode="json")
            conn.execute(
                "INSERT INTO personalization.receipt(account_id,kind,key,intent_hash,outcome) VALUES(%s,'reset',%s,%s,%s)",
                (authority.account_id, operation, fingerprint, Jsonb(outcome)),
            )
            return outcome

        return self.transactions.run("personalization", write)

    def claim_scope(self, identifier: UUID, participant: str, scope: str) -> dict:
        """Trusted installed participant API; never bound directly to browser input."""

        def write(conn):
            reset = conn.execute(
                "SELECT * FROM personalization.reset_responsibility WHERE id=%s FOR UPDATE",
                (identifier,),
            ).fetchone()
            if reset is None:
                raise PermissionError("reset unavailable")
            row = conn.execute(
                "SELECT *,clock_timestamp() AS now FROM personalization.reset_scope "
                "WHERE reset_id=%s AND participant=%s AND scope=%s FOR UPDATE",
                (identifier, participant, scope),
            ).fetchone()
            if (
                not row
                or row["disposition"] == "complete"
                or row["attempts"] >= self.policy.max_attempts
                or (row["lease_until"] and row["lease_until"] > row["now"])
            ):
                raise ValueError("reset scope not claimable")
            return conn.execute(
                "UPDATE personalization.reset_scope SET generation=generation+1,attempts=attempts+1,"
                "lease_until=clock_timestamp()+(%s*interval '1 second'),updated_at=clock_timestamp() "
                "WHERE reset_id=%s AND participant=%s AND scope=%s RETURNING *",
                (self.policy.lease_seconds, identifier, participant, scope),
            ).fetchone()

        return self.transactions.run("personalization", write)

    def record_scope(
        self,
        identifier: UUID,
        participant: str,
        scope: str,
        generation: int,
        *,
        evidence: UUID | None,
        reason: str,
    ) -> dict:
        """Commit the participant's evidence only under the current attempt fence."""
        if not reason or len(reason.encode()) > 128:
            raise ValueError("bounded reason required")

        def write(conn):
            reset = conn.execute(
                "SELECT * FROM personalization.reset_responsibility WHERE id=%s FOR UPDATE",
                (identifier,),
            ).fetchone()
            row = conn.execute(
                "SELECT *,clock_timestamp() AS now FROM personalization.reset_scope "
                "WHERE reset_id=%s AND participant=%s AND scope=%s FOR UPDATE",
                (identifier, participant, scope),
            ).fetchone()
            if (
                not reset
                or not row
                or row["generation"] != generation
                or not row["lease_until"]
                or row["lease_until"] <= row["now"]
            ):
                raise ValueError("stale reset claim")
            disposition = "complete" if evidence else "blocked"
            if row["disposition"] == "complete":
                if row["evidence_ref"] != evidence:
                    raise ValueError("scope evidence conflict")
                return reset
            conn.execute(
                "UPDATE personalization.reset_scope SET disposition=%s,evidence_ref=%s,reason_key=%s,updated_at=clock_timestamp() "
                "WHERE reset_id=%s AND participant=%s AND scope=%s",
                (disposition, evidence, reason, identifier, participant, scope),
            )
            remaining = conn.execute(
                "SELECT count(*) AS n FROM personalization.reset_scope WHERE reset_id=%s AND disposition<>'complete'",
                (identifier,),
            ).fetchone()["n"]
            return conn.execute(
                "UPDATE personalization.reset_responsibility SET status_revision=status_revision+1,"
                "disposition=%s,reason_key=%s WHERE id=%s RETURNING *",
                (
                    "complete" if not remaining else "blocked" if not evidence else "pending",
                    "complete"
                    if not remaining
                    else "scope-blocked"
                    if not evidence
                    else "cleanup-pending",
                    identifier,
                ),
            ).fetchone()

        return self.transactions.run("personalization", write)
