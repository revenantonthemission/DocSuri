"""Private attachment storage primitives, only reachable after service policy approval."""

import hashlib
from uuid import uuid4

from psycopg.types.json import Jsonb

from .errors import ResearchError
from .repository import ResearchRepository


class ResearchAttachments(ResearchRepository):
    def begin(self, authority, context_id, media_type, byte_length, content_hash, policy):
        if (
            media_type not in {"application/pdf", "text/plain"}
            or type(byte_length) is not int
            or not 1 <= byte_length <= 2097152
        ):
            raise ResearchError("INVALID_ARGUMENT")

        def begin(conn):
            self.context(conn, authority, context_id)
            return conn.execute(
                "INSERT INTO research.attachment(id,context_id,owner_id,content_hash,media_type"
                ",byte_length,write_handle,expires_at,policy) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,clock_timestamp()+interval '5 minutes',%s) "
                "RETURNING *",
                (
                    uuid4(),
                    context_id,
                    authority.account_id,
                    content_hash,
                    media_type,
                    byte_length,
                    uuid4(),
                    Jsonb(policy),
                ),
            ).fetchone()

        return self.run(authority, begin)

    def read(self, authority, context_id, attachment_id):
        def read(conn):
            self.context(conn, authority, context_id)
            row = conn.execute(
                "SELECT * FROM research.attachment WHERE id=%s AND context_id=%s AND owner_id=%s",
                (attachment_id, context_id, authority.account_id),
            ).fetchone()
            if not row:
                raise ResearchError("NOT_FOUND")
            return row

        return self.run(authority, read)

    def store_bytes(self, authority, context_id, attachment_id, write_handle, content):
        if not isinstance(content, bytes) or not 1 <= len(content) <= 2097152:
            raise ResearchError("INVALID_ARGUMENT")

        def store(conn):
            self.context(conn, authority, context_id)
            row = conn.execute(
                "SELECT *,expires_at<=clock_timestamp() AS expired FROM research.attachment "
                "WHERE id=%s AND context_id=%s AND owner_id=%s FOR UPDATE",
                (attachment_id, context_id, authority.account_id),
            ).fetchone()
            if not row or str(row["write_handle"]) != str(write_handle):
                raise ResearchError("NOT_FOUND")
            if row["expired"] or row["disposition"] != "pending":
                raise ResearchError("CONFLICT")
            if (
                row["byte_length"] != len(content)
                or row["content_hash"] != hashlib.sha256(content).hexdigest()
            ):
                raise ResearchError("INVALID_ARGUMENT")
            return conn.execute(
                "UPDATE research.attachment SET content=%s WHERE id=%s RETURNING *",
                (content, attachment_id),
            ).fetchone()

        return self.run(authority, store)

    def finish(self, authority, context_id, attachment_id, disposition, extracted):
        if disposition not in {
            "extracted",
            "unsupported",
            "malformed",
            "truncated",
            "protected",
            "failed",
        }:
            raise ResearchError("INVALID_ARGUMENT")
        if extracted is not None and (
            not isinstance(extracted, str) or len(extracted.encode()) > 32768
        ):
            raise ResearchError("INVALID_ARGUMENT")

        def finish(conn):
            self.context(conn, authority, context_id)
            row = conn.execute(
                "SELECT * FROM research.attachment WHERE id=%s AND context_id=%s AND "
                "owner_id=%s FOR UPDATE",
                (attachment_id, context_id, authority.account_id),
            ).fetchone()
            if not row:
                raise ResearchError("NOT_FOUND")
            if row["disposition"] != "pending":
                return row
            if row["content"] is None:
                raise ResearchError("CONFLICT")
            return conn.execute(
                "UPDATE research.attachment SET disposition=%s,extracted=%s,revision=revision+1"
                " WHERE id=%s RETURNING *",
                (disposition, extracted, attachment_id),
            ).fetchone()

        return self.run(authority, finish)
