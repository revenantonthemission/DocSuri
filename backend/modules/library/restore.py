"""Offline Library restriction reconciliation for an explicitly quarantined copy."""

from docsuri_ops.u2_restore_context import (
    context_to_json,
    fragment_digest,
    validate_fragment,
)
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
        queries = (
            (
                "boundary",
                "SELECT to_jsonb(t) AS value FROM library.history_boundary t "
                "ORDER BY account_id LIMIT 2001",
            ),
            (
                "restriction",
                "SELECT to_jsonb(t) AS value FROM library.restriction t "
                "ORDER BY account_id LIMIT 2001",
            ),
            (
                "saved-paper",
                "SELECT jsonb_build_object('account_id',account_id,"
                "'paper_id',paper_id,'revision',revision) AS value "
                "FROM library.saved_paper ORDER BY account_id,paper_id LIMIT 2001",
            ),
            (
                "saved-query",
                "SELECT jsonb_build_object('account_id',account_id,"
                "'id',id,'revision',revision) AS value "
                "FROM library.saved_query ORDER BY account_id,id LIMIT 2001",
            ),
            (
                "receipt",
                "SELECT to_jsonb(t) AS value FROM library.receipt t "
                "WHERE kind IN ('clear-history','remove-paper','remove-query') "
                "ORDER BY account_id,kind,key LIMIT 2001",
            ),
        )
        for kind, statement in queries:
            rows = conn.execute(statement).fetchall()
            if len(rows) > 2000:
                raise ValueError("Library checkpoint would be incomplete")
            records.extend({"kind": kind, "value": row["value"]} for row in rows)
        return records

    fragment = {
        "owner": "Library",
        "version": 1,
        "runId": context.run_id,
        "checkpointId": str(context.checkpoint_id),
        "sequence": context.sequence,
        "records": transactions.run("library", capture),
    }
    validate_fragment(context, fragment)
    return fragment


def reconcile_restore(transactions, fragment, context):
    digest = fragment_digest(context, fragment)
    if fragment["owner"] != "Library":
        raise ValueError("Library checkpoint required")
    row = transactions.run(
        "library",
        lambda conn: conn.execute(
            "SELECT library.reconcile_restore(%s,%s,%s) AS evidence",
            (Jsonb(context_to_json(context)), Jsonb(fragment), digest),
        ).fetchone(),
    )
    return {
        "owner": "Library",
        "evidenceRef": str(row["evidence"]),
        "checkpointId": str(context.checkpoint_id),
        "sequence": context.sequence,
        "fragmentDigest": digest,
        "disposition": "reconciled",
    }
