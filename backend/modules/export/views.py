"""Wire projections of the export store's rows (C09 2.1.0).

Every function turns a raw snake_case row from the repository into the camelCase shape
of one generated wire model, so the routes only validate and serialize. Revisions are
strings on the wire; optional fields are left out when they hold nothing, never sent as
null, except where the frozen shape requires the key (`expiresAt`, `remoteReference`,
`remoteUrl`, `reconciliationEvidenceHash`, `nextCursor`). No projection reads a
`sealed_token`, a token or provider text: rows carry none.
"""

import datetime as dt
from collections.abc import Mapping

from backend.u6_policy import ExportPolicy

# The placeholder title of an untitled Notion page (BR1.5); the wire requires a title.
UNTITLED = "제목 없음"
# The only page format U6 writes: one page with content under a parent page.
FORMAT_REVISION = "1"
# A synthetic composition can reach only the fake Notion (BR8.1).
SYNTHETIC_LIMITATION = "synthetic-only"


def _time(value: dt.datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _optional(target: dict, **values) -> dict:
    for key, value in values.items():
        if value is not None:
            target[key] = value
    return target


def scope_ids(policy: ExportPolicy) -> list[str]:
    """`destinationScopeIds`: the activation destination in the real composition only."""
    activation = policy.activation_destination_id
    return [activation] if activation is not None else []


def connection_view(row: Mapping, policy: ExportPolicy) -> dict:
    """ExportConnection: never credential material (BR1.1)."""
    limitations = [str(item) for item in row.get("limitations") or []]
    if policy.synthetic_only and SYNTHETIC_LIMITATION not in limitations:
        limitations.append(SYNTHETIC_LIMITATION)
    view = {
        "connectionId": str(row["id"]),
        "ownerId": str(row["account_id"]),
        "revision": str(row["revision"]),
        "provider": "notion",
        "state": row["state"],
        "destinationScopeIds": scope_ids(policy),
        "limitations": limitations,
    }
    return _optional(view, workspaceName=row.get("workspace_name"))


def replayed_connection_view(response: Mapping, owner: str, policy: ExportPolicy) -> dict:
    """A configure replay whose connection has moved on: the recorded identifiers, state
    and revision, which are all the replay record keeps (security design §3)."""
    return connection_view(
        {
            "id": response["connectionId"],
            "account_id": owner,
            "revision": response["revision"],
            "state": response["state"],
            "limitations": [],
        },
        policy,
    )


def destination_entry(
    *,
    connection_id: str,
    workspace_id: str,
    destination_id: str,
    title: str | None,
    context: str | None,
    readable: bool | None,
    creation_capability: str | None,
    writable: bool | None,
) -> dict:
    """ExportDestinationEntry: the frozen ExportDestination fields plus the A1 and S2
    facts; the parent page is the destination."""
    entry = {
        "connectionId": connection_id,
        "workspaceId": workspace_id,
        "parentPageId": destination_id,
        "formatRevision": FORMAT_REVISION,
        "destinationId": destination_id,
        "title": title or UNTITLED,
    }
    return _optional(
        entry,
        context=context,
        readable=readable,
        creationCapability=creation_capability,
        writable=writable,
    )


def preview_view(row: Mapping) -> dict:
    """ExportPreview of one stored revision (the destination snapshot is an entry)."""
    view = {
        "previewId": str(row["preview_id"]),
        "ownerId": str(row["account_id"]),
        "revision": str(row["revision"]),
        "source": {
            "artifactId": str(row["artifact_id"]),
            "revision": row["source_revision"],
            "contentHash": row["source_content_hash"],
        },
        "sourceEligibilityRevision": row["source_eligibility_revision"],
        "connectionRevision": str(row["connection_revision"]),
        "destination": dict(row["destination"]),
        "renderedText": row["rendered_text"],
        "renderedContentHash": row["rendered_content_hash"],
        "bindingHash": row["binding_hash"],
        "renderPolicy": dict(row["render_policy"]),
        "earlierExports": list(row["earlier_exports"] or []),
    }
    return _optional(view, marker=row.get("marker"), sourceTitle=row.get("source_title"))


def approval_view(row: Mapping) -> dict:
    """ExportApproval; `invalidationReason` exactly when invalidated (A9); `expiresAt`
    always empty (BR3.5)."""
    view = {
        "approvalId": str(row["id"]),
        "ownerId": str(row["account_id"]),
        "previewId": str(row["preview_id"]),
        "previewRevision": str(row["preview_revision"]),
        "bindingHash": row["binding_hash"],
        "approvedAt": _time(row["approved_at"]),
        "expiresAt": _time(row.get("expires_at")),
        "state": row["state"],
        "policy": dict(row["policy"]),
    }
    return _optional(view, invalidationReason=row.get("invalidation_reason"))


def _next_check(effect: Mapping) -> str | None:
    if effect["state"] != "unknown" or effect.get("scanning_stopped_at") is not None:
        return None
    return _time(effect.get("next_check_at"))


def effect_view(read: Mapping) -> dict:
    """ExportEffect from the repository's effect read (A4)."""
    effect = read["effect"]
    view = {
        "effectId": str(effect["id"]),
        "approvalId": str(effect["approval_id"]),
        "ownerId": str(effect["account_id"]),
        "revision": str(effect["revision"]),
        "bindingHash": effect["binding_hash"],
        "state": effect["state"],
        "remoteReference": effect.get("remote_reference"),
        "remoteUrl": effect.get("remote_url"),
        "reconciliationEvidenceHash": effect.get("reconciliation_evidence_hash"),
        "limitations": [str(item) for item in effect.get("limitations") or []],
        "settlementOffered": bool(read["settlementOffered"]),
    }
    return _optional(
        view,
        outcomeReason=effect.get("outcome_reason"),
        settledBy=effect.get("settled_by"),
        nextCheckAt=_next_check(effect),
    )


def _history_effect(read: Mapping) -> dict:
    effect = read["effect"]
    view = {
        "effectId": str(effect["id"]),
        "state": effect["state"],
        "revision": str(effect["revision"]),
        "possibleDuplicates": list(read["possibleDuplicates"]),
        "settlementOffered": bool(read["settlementOffered"]),
    }
    return _optional(
        view,
        remoteUrl=effect.get("remote_url"),
        outcomeReason=effect.get("outcome_reason"),
        settledBy=effect.get("settled_by"),
        nextCheckAt=_next_check(effect),
    )


def history_view(page: Mapping) -> dict:
    """ExportHistoryPage (A2). `endedAt` is the bound effect's end; an approval keeps
    no end time of its own, so a cancelled or invalidated approval carries none."""
    entries = []
    for item in page["entries"]:
        approval = item["approval"]
        destination = item.get("destination") or {}
        entry = {
            "approvalId": str(approval["id"]),
            "previewId": str(approval["preview_id"]),
            "previewRevision": str(approval["preview_revision"]),
            "bindingHash": approval["binding_hash"],
            "state": approval["state"],
            "approvedAt": _time(approval["approved_at"]),
            "sourceTitle": item["sourceTitle"],
            "destinationTitle": destination.get("title") or UNTITLED,
            "continuable": bool(item["continuable"]),
        }
        read = item.get("effect")
        if read is not None:
            entry["effect"] = _history_effect(read)
            _optional(entry, endedAt=_time(read["effect"].get("ended_at")))
        _optional(entry, invalidationReason=approval.get("invalidation_reason"))
        entries.append(entry)
    return {"entries": entries, "nextCursor": page["nextCursor"]}
