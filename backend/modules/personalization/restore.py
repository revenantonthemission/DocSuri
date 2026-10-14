"""Offline settings/reset restriction reconciliation, never a browser operation."""

from docsuri_ops.u2_restore_context import context_to_json, fragment_digest, validate_fragment
from psycopg.types.json import Jsonb


def export_restrictions(transactions, context, *, accounts_fragment):
    validate_fragment(context, accounts_fragment)
    if accounts_fragment["owner"] != "AccountAccess":
        raise ValueError("current AccountAccess checkpoint required")
    erased = sorted(
        {
            row["accountId"]
            for row in accounts_fragment["records"]
            if row.get("kind") == "account" and row.get("lifecycleState") == "erased"
        }
    )

    def capture(conn):
        records = [{"kind": "erased-owner", "account_id": value} for value in erased]
        for kind, table, ordering in (
            ("settings", "settings", "account_id"),
            ("reset", "reset_responsibility", "account_id,input_boundary"),
            ("scope", "reset_scope", "reset_id,participant,scope"),
            ("receipt", "receipt", "account_id,kind,key"),
        ):
            # Table and ordering are compile-time owner constants, never input.
            rows = conn.execute(
                f"SELECT to_jsonb(t) AS value FROM personalization.{table} t "
                f"ORDER BY {ordering} LIMIT 2001"
            ).fetchall()
            if len(rows) > 2000:
                raise ValueError("Personalization checkpoint would be incomplete")
            records.extend({"kind": kind, "value": row["value"]} for row in rows)
        return records

    fragment = {
        "owner": "Personalization",
        "version": 1,
        "runId": context.run_id,
        "checkpointId": str(context.checkpoint_id),
        "sequence": context.sequence,
        "records": transactions.run("personalization", capture),
    }
    validate_fragment(context, fragment)
    return fragment


def reconcile_restore(transactions, fragment, context):
    digest = fragment_digest(context, fragment)
    if fragment["owner"] != "Personalization":
        raise ValueError("Personalization checkpoint required")
    row = transactions.run(
        "personalization",
        lambda conn: conn.execute(
            "SELECT personalization.reconcile_restore(%s,%s,%s) AS evidence",
            (Jsonb(context_to_json(context)), Jsonb(fragment), digest),
        ).fetchone(),
    )
    return {
        "owner": "Personalization",
        "evidenceRef": str(row["evidence"]),
        "checkpointId": str(context.checkpoint_id),
        "sequence": context.sequence,
        "fragmentDigest": digest,
        "disposition": "reconciled",
    }
