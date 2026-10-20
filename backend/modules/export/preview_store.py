"""Preview units of the export store: one previewId per export pair, and immutable,
consecutively numbered revisions (BR2.3).

Each preparation locks its pair and adds the next revision with its frozen tree, text,
hashes, marker and earlier-export summaries (BR2.5). The revision number is assigned by
the schema's insert guard (`current_revision + 1`, which also advances the pair); the
marker and the binding hash cover the preview id and that revision, so the caller's
pure render function receives both inside the same transaction.
"""

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from .errors import ExportError
from .store_support import (
    REVISION_COLUMNS,
    invalid,
    is_hex64,
    not_found,
    require_now,
    require_revision,
    require_text,
    require_uuid,
)

EARLIER_LIMIT = 20
_HEX32 = frozenset("0123456789abcdef")


def require_destination_id(value, field: str = "destinationId") -> str:
    if not isinstance(value, str) or len(value) != 32 or not set(value) <= _HEX32:
        invalid(field)
    return value


@dataclass(frozen=True)
class PreviewFacts:
    """The source and binding facts of one preparation, read before the transaction."""

    artifact_id: UUID
    destination_id: str
    source_revision: str
    source_content_hash: str
    source_eligibility_revision: str
    source_title: str
    connection_id: UUID
    connection_revision: int
    destination: dict
    render_policy: dict

    def __post_init__(self):
        require_uuid(self.artifact_id, "artifactId")
        require_destination_id(self.destination_id)
        require_text(self.source_revision, "sourceRevision", limit=128)
        if not is_hex64(self.source_content_hash):
            invalid("sourceContentHash")
        require_text(self.source_eligibility_revision, "sourceEligibilityRevision", limit=128)
        require_text(self.source_title, "sourceTitle", limit=8000)
        require_uuid(self.connection_id, "connectionId")
        require_revision(self.connection_revision, "connectionRevision")
        if not isinstance(self.destination, dict) or not isinstance(self.render_policy, dict):
            invalid("destination")


@dataclass(frozen=True)
class RenderedRevision:
    """What the render policy produces for one (previewId, revision)."""

    marker: str
    rendered_blocks: dict
    rendered_text: str
    rendered_content_hash: str
    binding_hash: str

    def __post_init__(self):
        require_text(self.marker, "marker", limit=200)
        if not isinstance(self.rendered_blocks, dict):
            invalid("renderedBlocks")
        if not isinstance(self.rendered_text, str) or len(self.rendered_text.encode()) > 2_000_000:
            invalid("renderedText")
        if not is_hex64(self.rendered_content_hash) or not is_hex64(self.binding_hash):
            invalid("hash")


Render = Callable[[UUID, int], RenderedRevision]


def earlier_exports(conn, account_id: UUID, artifact_id: UUID, destination_id: str) -> list:
    """BR2.5: succeeded exports of the pair with their link, and those that may exist in
    Notion (not found after checks, or settled by the owner as not delivered)."""
    rows = conn.execute(
        "SELECT id,state,outcome_reason,ended_at,remote_url FROM export.effect "
        "WHERE account_id=%s AND artifact_id=%s AND destination_id=%s AND ("
        "state='succeeded' OR (state='failed' AND outcome_reason IN "
        "('not-found-after-checks','owner-settled-not-delivered'))) "
        "ORDER BY ended_at DESC,id DESC LIMIT %s",
        (account_id, artifact_id, destination_id, EARLIER_LIMIT),
    ).fetchall()
    summaries = []
    for row in rows:
        entry = {
            "effectId": str(row["id"]),
            "disposition": "exported" if row["state"] == "succeeded" else "may-exist",
            "endedAt": row["ended_at"].isoformat(),
        }
        if row["remote_url"] is not None:
            entry["remoteUrl"] = row["remote_url"]
        if row["outcome_reason"] is not None:
            entry["outcomeReason"] = row["outcome_reason"]
        summaries.append(entry)
    return summaries


def _locked_pair(conn, account_id: UUID, artifact_id: UUID, destination_id: str):
    conn.execute(
        "INSERT INTO export.preview_pair(preview_id,account_id,artifact_id,destination_id) "
        "VALUES(%s,%s,%s,%s) ON CONFLICT (account_id,artifact_id,destination_id) DO NOTHING",
        (uuid4(), account_id, artifact_id, destination_id),
    )
    return conn.execute(
        "SELECT preview_id,current_revision FROM export.preview_pair "
        "WHERE account_id=%s AND artifact_id=%s AND destination_id=%s FOR UPDATE",
        (account_id, artifact_id, destination_id),
    ).fetchone()


def owned_revision(conn, account_id: UUID, preview_id: UUID, revision: int | None):
    """One preview revision of the owner's pair (the current one when `revision` is
    None), with the pair's identity; foreign and absent raise LookupError alike."""
    row = conn.execute(
        f"SELECT {', '.join('r.' + c for c in REVISION_COLUMNS.split(','))},"
        "p.account_id,p.artifact_id,p.destination_id,p.current_revision "
        "FROM export.preview_pair p JOIN export.preview_revision r "
        "ON r.preview_id=p.preview_id AND r.revision=coalesce(%s,p.current_revision) "
        "WHERE p.preview_id=%s AND p.account_id=%s",
        (revision, preview_id, account_id),
    ).fetchone()
    if row is None:
        not_found()
    return row


class PreviewUnits:
    def add_preview_revision(
        self, authority, facts: PreviewFacts, render: Render, *, now: dt.datetime
    ) -> dict:
        """Freeze the next revision of the owner's export pair. CONFLICT when the
        connection is no longer connected at the revision the facts were read under."""
        if not isinstance(facts, PreviewFacts) or not callable(render):
            invalid("preview")
        require_now(now)

        def prepare(conn):
            current = conn.execute(
                "SELECT revision,state FROM export.connection WHERE id=%s AND account_id=%s",
                (facts.connection_id, authority.account_id),
            ).fetchone()
            if (
                current is None
                or current["state"] != "connected"
                or current["revision"] != facts.connection_revision
            ):
                revision = current["revision"] if current else None
                raise ExportError("CONFLICT", current={"connectionRevision": revision})
            pair = _locked_pair(conn, authority.account_id, facts.artifact_id, facts.destination_id)
            revision = pair["current_revision"] + 1
            summaries = earlier_exports(
                conn, authority.account_id, facts.artifact_id, facts.destination_id
            )
            rendered = render(pair["preview_id"], revision)
            if not isinstance(rendered, RenderedRevision):
                invalid("rendered")
            conn.execute(
                "INSERT INTO export.preview_revision(preview_id,revision,source_revision,"
                "source_content_hash,source_eligibility_revision,source_title,connection_id,"
                "connection_revision,destination,render_policy,marker,rendered_blocks,"
                "rendered_text,rendered_content_hash,binding_hash,earlier_exports,prepared_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    pair["preview_id"],
                    revision,
                    facts.source_revision,
                    facts.source_content_hash,
                    facts.source_eligibility_revision,
                    facts.source_title,
                    facts.connection_id,
                    facts.connection_revision,
                    Jsonb(facts.destination),
                    Jsonb(facts.render_policy),
                    rendered.marker,
                    Jsonb(rendered.rendered_blocks),
                    rendered.rendered_text,
                    rendered.rendered_content_hash,
                    rendered.binding_hash,
                    Jsonb(summaries),
                    now,
                ),
            )
            return owned_revision(conn, authority.account_id, pair["preview_id"], revision)

        return self.run(authority, prepare)

    def read_preview(self, authority, preview_id: UUID, revision: int | None = None) -> dict:
        """One revision of the owner's pair, the current one by default."""
        require_uuid(preview_id, "previewId")
        if revision is not None:
            require_revision(revision, "previewRevision")
        return self.run(
            authority,
            lambda conn: owned_revision(conn, authority.account_id, preview_id, revision),
        )
