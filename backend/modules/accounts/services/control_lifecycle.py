"""Owner-scoped lifecycle tickets; completion requires every installed scope."""

from __future__ import annotations

import hmac
import json
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from backend.modules.accounts.control_repository import ControlRepository
from backend.modules.accounts.services.guarded_entry import SessionTransport
from backend.transactions import Authority, guard
from docsuri_shared.workspace import wire
from psycopg.types.json import Jsonb


class ControlLifecycleService:
    def __init__(self, entry, manifest: tuple[tuple[str, str], ...], *, revision: str):
        if (
            not manifest
            or len(manifest) > entry.control_policy.max_scopes
            or len(set(manifest)) != len(manifest)
            or not revision
        ):
            raise ValueError("complete unique finite lifecycle manifest required")
        self.entry, self.transactions = entry, entry.transactions
        self.manifest, self.revision = tuple(sorted(manifest)), revision

    def request(
        self,
        authority: Authority,
        operation: UUID,
        expected: UUID,
        action: str,
        password: str | None,
        *,
        confirmation: UUID | None = None,
    ) -> dict:
        if action not in ("withdraw", "erase"):
            raise ValueError("unsupported lifecycle action")
        if confirmation is None:
            if password is None:
                raise PermissionError("recent reauthentication required")
            self.entry.reauthenticate(authority, password)
        intent = {
            "expectedRevision": str(expected),
            "action": action,
            "manifest": self.manifest,
            "manifestRevision": self.revision,
            "policy": self.entry.control_policy.reference,
        }

        def write(conn):
            guard(conn, authority, purpose="account-control")
            row = conn.execute(
                "SELECT * FROM accounts.account WHERE id=%s FOR UPDATE", (authority.account_id,)
            ).fetchone()
            digest, prior = ControlRepository.replay(
                conn, authority.account_id, "lifecycle", operation, intent
            )
            if prior is not None:
                return prior
            if row["lifecycle_revision"] != expected:
                raise ValueError("stale lifecycle revision")
            if confirmation is not None:
                confirmed = conn.execute(
                    "SELECT *,expires_at>clock_timestamp() AS fresh FROM accounts.control_proof WHERE id=%s AND account_id=%s FOR UPDATE",
                    (confirmation, authority.account_id),
                ).fetchone()
                if (
                    not confirmed
                    or confirmed["purpose"] != "reauthenticate"
                    or not confirmed["fresh"]
                    or confirmed["consumed_at"]
                    or confirmed["authority_revision"] != row["authority_revision"]
                    or confirmed["lifecycle_revision"] != expected
                    or confirmed["flow_hash"]
                    != self.entry.verifier("confirmation-session", str(authority.session_id))
                ):
                    raise PermissionError("lifecycle confirmation unavailable")
                bound = self.entry.reveal(
                    "proof:" + str(confirmation), confirmed["protected_payload"]
                )
                if bound != {
                    "action": action,
                    "expectedRevision": str(expected),
                    "policy": self.entry.control_policy.reference,
                }:
                    raise PermissionError("lifecycle confirmation binding mismatch")
            identifier, revision = uuid4(), uuid4()
            request = conn.execute(
                "INSERT INTO accounts.lifecycle_request(id,account_id,revision,action,policy_ref,manifest_revision,manifest,disposition,reason_key) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,'pending','owner-cleanup-pending') RETURNING accepted_at",
                (
                    identifier,
                    authority.account_id,
                    revision,
                    action,
                    Jsonb(self.entry.control_policy.reference),
                    self.revision,
                    Jsonb(self.manifest),
                ),
            ).fetchone()
            for participant, scope in self.manifest:
                conn.execute(
                    "INSERT INTO accounts.lifecycle_scope(request_id,participant,scope) VALUES(%s,%s,%s)",
                    (identifier, participant, scope),
                )
            state = "erased" if action == "erase" else "withdrawn"
            conn.execute(
                "UPDATE accounts.account SET active=false,lifecycle_state=%s,lifecycle_revision=%s,authority_revision=gen_random_uuid() WHERE id=%s",
                (state, revision, authority.account_id),
            )
            conn.execute(
                "UPDATE accounts.session SET revoked=true WHERE account_id=%s",
                (authority.account_id,),
            )
            consents = conn.execute(
                "SELECT purpose,granted,revision::text FROM accounts.consent WHERE account_id=%s ORDER BY purpose",
                (authority.account_id,),
            ).fetchall()
            conn.execute(
                "INSERT INTO accounts.current_restriction(account_id,generation,lifecycle_revision,disposition,consent) VALUES(%s,1,%s,%s,%s) "
                "ON CONFLICT(account_id) DO UPDATE SET generation=accounts.current_restriction.generation+1,lifecycle_revision=excluded.lifecycle_revision,"
                "disposition=excluded.disposition,consent=excluded.consent,updated_at=clock_timestamp()",
                (authority.account_id, revision, state, Jsonb(consents)),
            )
            outcome = {
                "requestId": str(identifier),
                "revision": str(revision),
                "disposition": "pending",
                "acceptedAt": request["accepted_at"].isoformat(),
                "accessRevoked": True,
            }
            if confirmation is not None:
                conn.execute(
                    "UPDATE accounts.control_proof SET consumed_at=clock_timestamp(),operation_id=%s,outcome=%s WHERE id=%s",
                    (operation, Jsonb(outcome), confirmation),
                )
            return ControlRepository.record(
                conn, authority.account_id, "lifecycle", operation, digest, outcome
            )

        return self.transactions.run("accounts", write)

    def prepare_confirmation(
        self, authority: Authority, operation: UUID, expected: UUID, action: str, password: str
    ) -> dict:
        if action not in ("withdraw", "erase"):
            raise ValueError("unsupported lifecycle action")
        self.entry.reauthenticate(authority, password)
        intent = {
            "action": action,
            "expectedRevision": str(expected),
            "policy": self.entry.control_policy.reference,
        }

        def write(conn):
            guard(conn, authority, purpose="account-control")
            account = conn.execute(
                "SELECT * FROM accounts.account WHERE id=%s FOR UPDATE", (authority.account_id,)
            ).fetchone()
            digest, prior = ControlRepository.replay(
                conn, authority.account_id, "lifecycle-confirm", operation, intent
            )
            if prior is not None:
                return prior
            if account["lifecycle_revision"] != expected:
                raise ValueError("stale lifecycle revision")
            identifier = uuid4()
            row = conn.execute(
                "INSERT INTO accounts.control_proof(id,account_id,purpose,proof_hash,flow_hash,authority_revision,lifecycle_revision,protected_payload,key_version,expires_at) "
                "VALUES(%s,%s,'reauthenticate',%s,%s,%s,%s,%s,'u2-v1',clock_timestamp()+(%s*interval '1 second')) RETURNING expires_at",
                (
                    identifier,
                    authority.account_id,
                    self.entry.verifier("confirmation", str(identifier)),
                    self.entry.verifier("confirmation-session", str(authority.session_id)),
                    account["authority_revision"],
                    expected,
                    self.entry.protect("proof:" + str(identifier), intent),
                    self.entry.control_policy.proof_seconds,
                ),
            ).fetchone()
            return ControlRepository.record(
                conn,
                authority.account_id,
                "lifecycle-confirm",
                operation,
                digest,
                {
                    "confirmationRef": str(identifier),
                    "action": action,
                    "revision": str(expected),
                    "expiresAt": row["expires_at"].isoformat(),
                },
            )

        return self.transactions.run("accounts", write)

    def request_confirmed(
        self, authority: Authority, operation: UUID, confirmation: UUID, action: str
    ) -> dict:
        row = self.transactions.run(
            "accounts",
            lambda conn: conn.execute(
                "SELECT lifecycle_revision FROM accounts.control_proof WHERE id=%s AND account_id=%s",
                (confirmation, authority.account_id),
            ).fetchone(),
        )
        if not row:
            raise PermissionError("lifecycle confirmation unavailable")
        return self.request(
            authority, operation, row["lifecycle_revision"], action, None, confirmation=confirmation
        )

    def request_browser(
        self, token: str, csrf: str, operation: UUID, confirmation: UUID, action: str
    ) -> dict:
        """A revoked cookie can recover only its exact already-accepted operation."""
        try:
            current = self.entry._current_session(token, csrf=csrf)
        except PermissionError:

            def recover(conn):
                session = conn.execute(
                    "SELECT * FROM accounts.session WHERE token_hash=%s",
                    (self.entry.verifier("session", token),),
                ).fetchone()
                if not session or session["csrf_hash"] != self.entry.verifier("csrf", csrf):
                    raise PermissionError("lifecycle receipt unavailable")
                account = conn.execute(
                    "SELECT * FROM accounts.account WHERE id=%s FOR SHARE", (session["account_id"],)
                ).fetchone()
                proof = conn.execute(
                    "SELECT * FROM accounts.control_proof WHERE id=%s AND account_id=%s",
                    (confirmation, session["account_id"]),
                ).fetchone()
                if (
                    not proof
                    or not proof["consumed_at"]
                    or proof["operation_id"] != operation
                    or proof["purpose"] != "reauthenticate"
                    or proof["flow_hash"]
                    != self.entry.verifier("confirmation-session", str(session["id"]))
                ):
                    raise PermissionError("lifecycle receipt unavailable")
                bound = self.entry.reveal("proof:" + str(confirmation), proof["protected_payload"])
                if bound["action"] != action or proof["outcome"]["revision"] != str(
                    account["lifecycle_revision"]
                ):
                    raise PermissionError("lifecycle receipt unavailable")
                return proof["outcome"]

            return self.transactions.run("accounts", recover)
        return self.request_confirmed(
            Authority(current["account_id"], current["id"]), operation, confirmation, action
        )

    def status_transport(self, outcome: dict, operation: UUID) -> SessionTransport:
        """Issue one limited cookie only from a verified acceptance/proof outcome."""
        identifier = UUID(outcome["requestId"])
        token = self.entry.verifier("lifecycle-status", str(identifier) + ":" + str(operation))
        csrf = self.entry.verifier("session-csrf", token)
        session_id = uuid5(NAMESPACE_URL, str(identifier) + ":status")

        def write(conn):
            found = conn.execute(
                "SELECT account_id FROM accounts.lifecycle_request WHERE id=%s", (identifier,)
            ).fetchone()
            if not found:
                raise PermissionError("lifecycle request unavailable")
            account = conn.execute(
                "SELECT * FROM accounts.account WHERE id=%s FOR SHARE", (found["account_id"],)
            ).fetchone()
            request = conn.execute(
                "SELECT * FROM accounts.lifecycle_request WHERE id=%s", (identifier,)
            ).fetchone()
            if (
                str(request["revision"]) != outcome["revision"]
                or account["lifecycle_revision"] != request["revision"]
            ):
                raise PermissionError("superseded lifecycle request")
            conn.execute(
                "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,authority_revision,expires_at,purpose,flow_id) "
                "VALUES(%s,%s,%s,%s,%s,%s+(%s*interval '1 second'),'reactivation_status',%s) ON CONFLICT(id) DO NOTHING",
                (
                    session_id,
                    account["id"],
                    self.entry.verifier("session", token),
                    self.entry.verifier("csrf", csrf),
                    account["authority_revision"],
                    request["accepted_at"],
                    self.entry.control_policy.session_seconds,
                    identifier,
                ),
            )
            return {"lifecycleRequestId": str(identifier), "csrfToken": csrf}

        return SessionTransport(token, csrf, self.transactions.run("accounts", write))

    def inspect_limited(self, token: str, csrf: str, identifier: UUID) -> dict:
        def read(conn):
            session = conn.execute(
                "SELECT *,expires_at>clock_timestamp() AS fresh FROM accounts.session WHERE token_hash=%s",
                (self.entry.verifier("session", token),),
            ).fetchone()
            if (
                not session
                or session["purpose"] != "reactivation_status"
                or session["flow_id"] != identifier
                or session["revoked"]
                or not session["fresh"]
                or session["csrf_hash"] != self.entry.verifier("csrf", csrf)
            ):
                raise PermissionError("limited lifecycle authority unavailable")
            account = conn.execute(
                "SELECT * FROM accounts.account WHERE id=%s FOR SHARE", (session["account_id"],)
            ).fetchone()
            request = conn.execute(
                "SELECT * FROM accounts.lifecycle_request WHERE id=%s AND account_id=%s",
                (identifier, account["id"]),
            ).fetchone()
            if not request or account["lifecycle_revision"] != request["revision"]:
                raise PermissionError("superseded lifecycle authority")
            return self._status(conn, request, account)

        return self.transactions.run("accounts", read)

    def _status(self, conn, request: dict, account: dict) -> dict:
        rows = conn.execute(
            "SELECT * FROM accounts.lifecycle_scope WHERE request_id=%s ORDER BY participant,scope LIMIT %s",
            (request["id"], self.entry.control_policy.max_scopes + 1),
        ).fetchall()
        if not rows or len(rows) > self.entry.control_policy.max_scopes:
            raise RuntimeError("incomplete lifecycle manifest")
        groups = {}
        for row in rows:
            complete = row["disposition"] == "complete"
            scope = {
                "scope": row["scope"],
                "disposition": (
                    "erased"
                    if request["action"] == "erase"
                    and row["reason_key"]
                    not in (
                        "bounded-audit-identifiers-retained",
                        "external-copies-retained-by-owner",
                    )
                    else "retained_by_policy"
                )
                if complete
                else row["disposition"],
                "reasonKey": row["reason_key"],
            }
            if complete:
                scope["evidenceReference"] = str(row["evidence_ref"])
            groups.setdefault(row["participant"], []).append((scope, row))
        value = {
            "lifecycleRequestId": str(request["id"]),
            "accountId": str(account["id"]),
            "action": request["action"],
            "revision": str(request["revision"]),
            "policyRef": request["policy_ref"],
            "manifestRevision": request["manifest_revision"],
            "authorityRevision": str(account["authority_revision"]),
            "revocation": "not_required" if request["action"] == "reactivate" else "effective",
            "state": "accepted" if request["disposition"] == "pending" else request["disposition"],
            "participants": [
                {
                    "participantId": name,
                    "revision": str(request["status_generation"]),
                    "state": "acknowledged"
                    if all(s[1]["disposition"] == "complete" for s in scopes)
                    else "blocked"
                    if any(s[1]["disposition"] == "blocked" for s in scopes)
                    else "pending",
                    "scopes": [s[0] for s in scopes],
                    "observedAt": max(s[1]["updated_at"] for s in scopes).isoformat(),
                }
                for name, scopes in groups.items()
            ],
        }
        if request["disposition"] == "complete":
            value["completionEvidenceRef"] = str(request["id"])
        return wire.LifecycleRequest.model_validate(value).model_dump(
            mode="json", exclude_none=True
        )

    def claim(self, request: UUID, participant: str, scope: str) -> dict:
        if (participant, scope) not in self.manifest:
            raise PermissionError("unregistered lifecycle scope")

        def write(conn):
            found = conn.execute(
                "SELECT account_id FROM accounts.lifecycle_request WHERE id=%s", (request,)
            ).fetchone()
            if not found:
                raise PermissionError("lifecycle request unavailable")
            account = conn.execute(
                "SELECT lifecycle_revision FROM accounts.account WHERE id=%s FOR SHARE",
                (found["account_id"],),
            ).fetchone()
            row = conn.execute(
                "SELECT * FROM accounts.lifecycle_request WHERE id=%s FOR UPDATE", (request,)
            ).fetchone()
            if (
                row["revision"] != account["lifecycle_revision"]
                or row["manifest_revision"] != self.revision
            ):
                raise ValueError("superseded lifecycle request")
            ticket = conn.execute(
                "SELECT *,clock_timestamp() AS now FROM accounts.lifecycle_scope WHERE request_id=%s AND participant=%s AND scope=%s FOR UPDATE",
                (request, participant, scope),
            ).fetchone()
            if (
                not ticket
                or ticket["disposition"] == "complete"
                or ticket["attempts"] >= self.entry.control_policy.max_attempts
                or (ticket["lease_until"] and ticket["lease_until"] > ticket["now"])
            ):
                raise ValueError("lifecycle scope not claimable")
            ticket = conn.execute(
                "UPDATE accounts.lifecycle_scope SET generation=generation+1,attempts=attempts+1,lease_until=clock_timestamp()+(%s*interval '1 second') "
                "WHERE request_id=%s AND participant=%s AND scope=%s RETURNING *",
                (self.entry.control_policy.lease_seconds, request, participant, scope),
            ).fetchone()
            return dict(
                ticket,
                account_id=found["account_id"],
                lifecycle_revision=row["revision"],
                action=row["action"],
                policy_ref=row["policy_ref"],
                manifest_revision=row["manifest_revision"],
            )

        return self.transactions.run("accounts", write)

    def acknowledge(self, ticket: dict, *, evidence: UUID | None, reason: str) -> dict:
        if (ticket["participant"], ticket["scope"]) not in self.manifest or len(
            reason.encode()
        ) > 128:
            raise ValueError("lifecycle evidence outside manifest")

        def write(conn):
            account = conn.execute(
                "SELECT lifecycle_revision FROM accounts.account WHERE id=%s FOR UPDATE",
                (ticket["account_id"],),
            ).fetchone()
            row = conn.execute(
                "SELECT * FROM accounts.lifecycle_request WHERE id=%s FOR UPDATE",
                (ticket["request_id"],),
            ).fetchone()
            current = conn.execute(
                "SELECT *,clock_timestamp() AS now FROM accounts.lifecycle_scope WHERE request_id=%s AND participant=%s AND scope=%s FOR UPDATE",
                (ticket["request_id"], ticket["participant"], ticket["scope"]),
            ).fetchone()
            if (
                not account
                or not row
                or not current
                or row["account_id"] != ticket["account_id"]
                or account["lifecycle_revision"] != row["revision"]
                or row["revision"] != ticket["lifecycle_revision"]
                or row["policy_ref"] != ticket["policy_ref"]
                or row["manifest_revision"] != ticket["manifest_revision"]
                or current["generation"] != ticket["generation"]
            ):
                raise ValueError("stale lifecycle evidence")
            if current["disposition"] == "complete":
                if current["evidence_ref"] != evidence:
                    raise ValueError("lifecycle evidence conflict")
                return row
            if not current["lease_until"] or current["lease_until"] <= current["now"]:
                raise ValueError("expired lifecycle claim")
            conn.execute(
                "UPDATE accounts.lifecycle_scope SET disposition=%s,evidence_ref=%s,reason_key=%s,updated_at=clock_timestamp() "
                "WHERE request_id=%s AND participant=%s AND scope=%s",
                (
                    "complete" if evidence else "blocked",
                    evidence,
                    reason,
                    ticket["request_id"],
                    ticket["participant"],
                    ticket["scope"],
                ),
            )
            remaining = conn.execute(
                "SELECT count(*) AS n FROM accounts.lifecycle_scope WHERE request_id=%s AND disposition<>'complete'",
                (ticket["request_id"],),
            ).fetchone()["n"]
            if not remaining and row["action"] == "reactivate":
                conn.execute(
                    "UPDATE accounts.account SET active=true,lifecycle_state='active',authority_revision=gen_random_uuid() WHERE id=%s",
                    (ticket["account_id"],),
                )
                conn.execute(
                    "UPDATE accounts.current_restriction SET disposition='active',lifecycle_revision=%s,generation=generation+1,updated_at=clock_timestamp() WHERE account_id=%s",
                    (row["revision"], ticket["account_id"]),
                )
            return conn.execute(
                "UPDATE accounts.lifecycle_request SET disposition=%s,reason_key=%s,status_generation=status_generation+1 WHERE id=%s RETURNING *",
                (
                    "complete" if not remaining else "pending" if evidence else "blocked",
                    "complete" if not remaining else "scope-unresolved",
                    ticket["request_id"],
                ),
            ).fetchone()

        return self.transactions.run("accounts", write)

    def evaluate_restore(self, account: UUID, snapshot_revision: UUID) -> dict:
        """Internal restore admission; callers must recheck at the restore effect."""

        def read(conn):
            row = conn.execute(
                "SELECT * FROM accounts.current_restriction WHERE account_id=%s FOR SHARE",
                (account,),
            ).fetchone()
            if row is None:
                return {
                    "decision": "requires_reconciliation",
                    "reasonKey": "current-restriction-evidence-missing",
                }
            decision = (
                "requires_reconciliation"
                if row["disposition"] == "active" and row["lifecycle_revision"] == snapshot_revision
                else "deny"
            )
            return {
                "decision": decision,
                "revision": str(row["lifecycle_revision"]),
                "generation": str(row["generation"]),
                "reasonKey": "owner-boundaries-require-reconciliation"
                if decision == "requires_reconciliation"
                else "current-restriction-enforced",
            }

        return self.transactions.run("accounts", read)

    def reactivate(self, operation: UUID, challenge: UUID, proof: str, flow_binding: str) -> dict:
        intent = self.entry.verifier(
            "reactivation-complete", json.dumps([str(challenge), proof, flow_binding])
        )

        def write(conn):
            found = conn.execute(
                "SELECT account_id FROM accounts.control_proof WHERE id=%s", (challenge,)
            ).fetchone()
            if not found:
                raise PermissionError("reactivation proof unavailable")
            account = conn.execute(
                "SELECT * FROM accounts.account WHERE id=%s FOR UPDATE", (found["account_id"],)
            ).fetchone()
            row = conn.execute(
                "SELECT *,expires_at>clock_timestamp() AS fresh FROM accounts.control_proof WHERE id=%s FOR UPDATE",
                (challenge,),
            ).fetchone()
            if (
                row["purpose"] != "reactivate"
                or not hmac.compare_digest(
                    row["proof_hash"], self.entry.verifier("reactivation-proof", proof)
                )
                or not hmac.compare_digest(
                    row["flow_hash"], self.entry.verifier("flow", flow_binding)
                )
                or account["lifecycle_state"] == "erased"
            ):
                raise PermissionError("reactivation proof unavailable")
            previous = conn.execute(
                "SELECT * FROM accounts.control_receipt WHERE account_id=%s AND kind='reactivate' AND key=%s",
                (account["id"], operation),
            ).fetchone()
            if previous:
                if (
                    previous["intent_hash"] != intent
                    or row["operation_id"] != operation
                    or previous["outcome"]["revision"] != str(account["lifecycle_revision"])
                ):
                    raise PermissionError("reactivation proof unavailable")
                return previous["outcome"]
            if (
                account["lifecycle_state"] != "withdrawn"
                or not row["fresh"]
                or row["consumed_at"]
                or row["lifecycle_revision"] != account["lifecycle_revision"]
                or row["authority_revision"] != account["authority_revision"]
            ):
                raise PermissionError("reactivation proof unavailable")
            identifier, revision = uuid4(), uuid4()
            conn.execute(
                "INSERT INTO accounts.lifecycle_request(id,account_id,revision,action,policy_ref,manifest_revision,manifest,disposition,reason_key) "
                "VALUES(%s,%s,%s,'reactivate',%s,%s,%s,'pending','restoration-evidence-pending')",
                (
                    identifier,
                    account["id"],
                    revision,
                    Jsonb(self.entry.control_policy.reference),
                    self.revision,
                    Jsonb(self.manifest),
                ),
            )
            for participant, scope in self.manifest:
                conn.execute(
                    "INSERT INTO accounts.lifecycle_scope(request_id,participant,scope) VALUES(%s,%s,%s)",
                    (identifier, participant, scope),
                )
            conn.execute(
                "UPDATE accounts.account SET lifecycle_revision=%s WHERE id=%s",
                (revision, account["id"]),
            )
            outcome = {
                "requestId": str(identifier),
                "revision": str(revision),
                "disposition": "reactivation_pending",
            }
            conn.execute(
                "UPDATE accounts.control_proof SET consumed_at=clock_timestamp(),operation_id=%s,outcome=%s WHERE id=%s",
                (operation, Jsonb(outcome), challenge),
            )
            return ControlRepository.record(
                conn, account["id"], "reactivate", operation, intent, outcome
            )

        return self.transactions.run("accounts", write)
