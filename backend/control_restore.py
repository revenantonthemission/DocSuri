"""Owner-specific restriction exports for the quarantined U2 restore protocol.

These fragments deliberately omit account credentials and private research text.
They are trusted only inside the verified, complete checkpoint envelope. Export
must run with writers stopped; individual owner transactions are not a global
snapshot and cannot substitute for the coordinator's exclusive process lock.
"""

from __future__ import annotations

from docsuri_ops.u2_restore_context import context_to_json, fragment_digest
from psycopg import sql
from psycopg.types.json import Jsonb


class OwnerRestore:
    owner: str
    schema: str
    queries: tuple[str, ...]

    @classmethod
    def export_restrictions(cls, source_tx, context, *, accounts_fragment=None):
        if source_tx.profile.run_id != context.run_id:
            raise ValueError("restore export run mismatch")

        def read(conn):
            records = []
            for query in cls.queries:
                rows = conn.execute(query + " LIMIT 2001").fetchall()
                records.extend(row["record"] for row in rows)
                if len(records) > 2000:
                    raise ValueError("complete owner checkpoint exceeds finite row bound")
            return records

        fragment = {
            "owner": cls.owner,
            "version": 1,
            "runId": context.run_id,
            "checkpointId": str(context.checkpoint_id),
            "sequence": context.sequence,
            "records": source_tx.run(cls.schema, read),
        }
        if cls.owner in {"PaperAssistance", "DiscoveryCitations"}:
            if accounts_fragment is None or accounts_fragment.get("owner") != "AccountAccess":
                raise ValueError("complete current account restrictions required")
            fragment_digest(context, accounts_fragment)
            fragment["records"].extend(
                {"kind": "erasedOwner", "accountId": row["accountId"]}
                for row in accounts_fragment["records"]
                if row.get("kind") == "account"
                and row.get("lifecycleState") in {"erasing", "erased"}
            )
        fragment_digest(context, fragment)
        return fragment

    @classmethod
    def reconcile_restore(cls, restore_tx, fragment, context):
        digest = fragment_digest(context, fragment)
        if fragment["owner"] != cls.owner:
            raise ValueError("restore owner mismatch")
        evidence = restore_tx.run(
            cls.schema,
            lambda conn: conn.execute(
                sql.SQL("SELECT {}.reconcile_restore(%s,%s,%s) AS evidence").format(
                    sql.Identifier(cls.schema)
                ),
                (Jsonb(context_to_json(context)), Jsonb(fragment), digest),
            ).fetchone()["evidence"],
        )
        return {
            "owner": cls.owner,
            "evidenceRef": str(evidence),
            "checkpointId": str(context.checkpoint_id),
            "sequence": context.sequence,
            "fragmentDigest": digest,
            "disposition": "reconciled",
        }


class AccountsRestore(OwnerRestore):
    owner, schema = "AccountAccess", "accounts"
    queries = (
        "SELECT jsonb_build_object('kind','account','accountId',a.id,"
        "'lifecycleState',a.lifecycle_state,"
        "'active',a.active,'verified',a.verified,'authorityRevision',a.authority_revision,"
        "'lifecycleRevision',a.lifecycle_revision,'credentialDigest',"
        "encode(sha256(convert_to(a.password_hash||'|'||a.email||'|'||a.role,'UTF8')),'hex')) "
        "AS record FROM accounts.account a ORDER BY a.id",
        "SELECT jsonb_build_object('kind','consent','accountId',account_id,'purpose',purpose,"
        "'granted',granted,'revision',revision,'effectiveAt',effective_at) AS record "
        "FROM accounts.consent ORDER BY account_id,purpose",
        "SELECT jsonb_build_object('kind','restriction','row',to_jsonb(r)) AS record "
        "FROM accounts.current_restriction r ORDER BY account_id",
        "SELECT jsonb_build_object('kind','request','row',to_jsonb(r)) AS record "
        "FROM accounts.lifecycle_request r ORDER BY accepted_at,id",
        "SELECT jsonb_build_object('kind','scope','row',to_jsonb(s)) AS record "
        "FROM accounts.lifecycle_scope s ORDER BY request_id,participant,scope",
    )


class UsageRestore(OwnerRestore):
    owner, schema = "UsageEntitlements", "usage"
    queries = (
        "SELECT jsonb_build_object('kind','entitlement','row',to_jsonb(r)) AS record "
        "FROM usage.entitlement r ORDER BY account_id",
        "SELECT jsonb_build_object('kind','reservation','row',to_jsonb(r)) AS record "
        "FROM usage.reservation r ORDER BY accepted_at,id",
        "SELECT jsonb_build_object('kind','rejected','row',to_jsonb(r)) AS record "
        "FROM usage.rejected_operation r ORDER BY operation_id",
    )


class AssistanceRestore(OwnerRestore):
    owner, schema = "PaperAssistance", "assistance"
    queries = (
        "SELECT jsonb_build_object('kind','admission','operationId',operation_id,"
        "'accountId',account_id,"
        "'intentHash',intent_hash,'generation',generation,'disposition',disposition,"
        "'reservationId',reservation_id,'periodId',period_id,'quantity',quantity,"
        "'policyRef',policy_ref,'closureRef',closure_ref,'closedAt',closed_at,"
        "'closureReason',closure_reason) AS record FROM assistance.admission ORDER BY operation_id",
        "SELECT jsonb_build_object('kind','job','id',id,'accountId',account_id,'state',state,"
        "'sequence',sequence,'fence',fence,'revision',revision,'phase',phase,'failureCode',failure_code,"
        "'settlementPending',settlement_pending,'settlementReceipt',settlement_receipt) AS record "
        "FROM assistance.job ORDER BY accepted_at,id",
        "SELECT jsonb_build_object('kind','result','id',id,'accountId',account_id,"
        "'availability',availability) AS record FROM assistance.result ORDER BY id",
        "SELECT jsonb_build_object('kind','erased','row',to_jsonb(r)) AS record "
        "FROM assistance.erased_admission r ORDER BY operation_id",
    )


class DiscoveryRestore(OwnerRestore):
    owner, schema = "DiscoveryCitations", "discovery"
    queries = (
        "SELECT jsonb_build_object('kind','boundary','accountId',account_id,'sequence',sequence) "
        "AS record FROM discovery.owner_admission ORDER BY account_id",
        "SELECT jsonb_build_object('kind','admission','row',to_jsonb(r)) AS record "
        "FROM discovery.admission r ORDER BY account_id,sequence",
        "SELECT jsonb_build_object('kind','execution','id',id,'accountId',account_id,"
        "'relayState',relay_state) AS record FROM discovery.execution ORDER BY id",
    )
