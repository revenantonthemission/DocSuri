"""Atomic owner-local lifecycle effects with current AccountAccess ticket fencing."""

from __future__ import annotations

from uuid import uuid4

from psycopg import sql
from psycopg.types.json import Jsonb


def apply_owner_effect(transactions, owner, scopes, ticket, effect):
    participant = {"library": "Library", "personalization": "Personalization"}[owner]
    if ticket["participant"] != participant or ticket["scope"] not in scopes:
        raise PermissionError("unregistered lifecycle participant scope")

    def write(conn):
        action = conn.execute(
            "SELECT accounts.lifecycle_effect_action(%s,%s,%s,%s,%s,%s,%s) AS action",
            (
                ticket["request_id"],
                ticket["account_id"],
                participant,
                ticket["scope"],
                ticket["generation"],
                Jsonb(ticket["policy_ref"]),
                ticket["manifest_revision"],
            ),
        ).fetchone()["action"]
        prior = conn.execute(
            sql.SQL(
                "SELECT * FROM {}.lifecycle_evidence WHERE request_id=%s AND scope=%s FOR UPDATE"
            ).format(sql.Identifier(owner)),
            (ticket["request_id"], ticket["scope"]),
        ).fetchone()
        if prior:
            if (
                prior["policy_ref"] != ticket["policy_ref"]
                or prior["manifest_revision"] != ticket["manifest_revision"]
            ):
                raise ValueError("lifecycle evidence binding conflict")
            evidence = prior["evidence_ref"]
        else:
            effect(conn, action, ticket)
            evidence = uuid4()
        conn.execute(
            sql.SQL(
                "INSERT INTO {}.lifecycle_evidence(request_id,scope,generation,"
                "policy_ref,manifest_revision,evidence_ref) VALUES(%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT(request_id,scope) DO UPDATE SET generation=excluded.generation"
            ).format(sql.Identifier(owner)),
            (
                ticket["request_id"],
                ticket["scope"],
                ticket["generation"],
                Jsonb(ticket["policy_ref"]),
                ticket["manifest_revision"],
                evidence,
            ),
        )
        return {
            "evidenceRef": str(evidence),
            "reasonKey": "owner-scope-complete",
            "disposition": "complete",
        }

    return transactions.run(owner, write)
