"""ResearchWorkspace behavior and canonical read models in the shared release."""

import base64
import hashlib
import hmac
import json
import secrets
from urllib.parse import urlsplit
from uuid import uuid4

from backend.u4_policy import SYNTHETIC_RESEARCH

from .errors import ResearchError
from .jobs import ResearchJobs
from .repository import ResearchRepository


def context_dto(row):
    return {
        "contextId": str(row["id"]),
        "ownerId": str(row["owner_id"]),
        "revision": str(row["revision"]),
        "purpose": row["purpose"],
        "lifecycle": row["lifecycle"],
    }


def session_dto(row):
    jobs = row.get("jobs", [])
    return {
        "sessionId": str(row["id"]),
        "ownerId": str(row["owner_id"]),
        "revision": str(row["revision"]),
        "scope": row["scope"],
        "lifecycle": row["lifecycle"],
        "turnIds": [str(j["id"]) for j in jobs],
        "pendingJobIds": [
            str(j["id"]) for j in jobs if j["state"] in {"accepted", "running", "cancel_requested"}
        ],
        "deletionBoundary": str(row["revision"]) if row["lifecycle"] != "active" else None,
    }


def artifact_dto(row):
    return {
        "artifact": {
            "artifactId": str(row["id"]),
            "revision": str(row["revision"]),
            "contentHash": row["content_hash"],
        },
        "ownerId": str(row["owner_id"]),
        "contextId": str(row["context_id"]),
        "operationId": str(row["job_id"]),
        "kind": row["kind"],
        "output": row["output"],
        "currentEligibilityRevision": str(row["eligibility_revision"]),
        "mediaType": "application/json",
        "policy": row["policy"],
    }


class ResearchService:
    def __init__(self, transactions, corpus, *, execution=None, policy=SYNTHETIC_RESEARCH):
        self.repository = ResearchRepository(transactions)
        self.jobs = ResearchJobs(transactions)
        self.corpus = corpus
        self.execution = execution
        self.policy = policy
        self.cursor_key = secrets.token_bytes(32)

    def require_policy(self, value):
        if value != self.policy.reference():
            raise ResearchError("POLICY_UNRESOLVED")

    def scope(self, authority, scope):
        self.repository.run(
            authority, lambda conn: self.repository.context(conn, authority, scope["contextId"])
        )
        self.require_policy(scope["scopePolicy"])
        if len(scope["publicPapers"]) > 2 or len(scope["webReferences"]) > 8:
            raise ResearchError("INVALID_ARGUMENT")
        if scope["attachmentIds"]:
            raise ResearchError("POLICY_UNRESOLVED")
        for reference in scope["webReferences"]:
            try:
                parsed = urlsplit(reference)
                if (
                    parsed.scheme != "https"
                    or not parsed.hostname
                    or parsed.username
                    or parsed.password
                    or parsed.port not in (None, 443)
                ):
                    raise ValueError()
            except (ValueError, TypeError):
                raise ResearchError("SOURCE_INELIGIBLE") from None
        for paper in scope["publicPapers"]:
            source = self.corpus.read(paper["versionId"])
            if (
                source["paper_id"] != paper["paperId"]
                or str(source["eligibility_revision"]) != paper["eligibilityRevision"]
            ):
                raise ResearchError("SOURCE_INELIGIBLE")

    def create_context(self, authority, value, *, operation=None):
        self.require_policy(value["policy"])
        return context_dto(
            self.repository.create_context(authority, value["purpose"], operation=operation)
        )

    def create_session(self, authority, value, *, operation=None):
        self.scope(authority, value["scope"])
        return session_dto(
            self.repository.create_session(
                authority, value["title"], value["scope"], operation=operation
            )
        )

    def read_session(self, authority, value):
        return session_dto(self.repository.read_session(authority, value["sessionId"]))

    def list_sessions(self, authority, value):
        limit = value["page"].get("limit", self.policy.page_size)
        if type(limit) is not int or not 1 <= limit <= self.policy.page_size:
            raise ResearchError("INVALID_ARGUMENT")
        rows, revision = self.repository.session_snapshot(authority)
        offset = 0
        cursor = value["page"].get("cursor")
        if cursor:
            try:
                if len(cursor) > 2048:
                    raise ValueError()
                data, signature = cursor.split(".")
                expected = hmac.new(self.cursor_key, data.encode(), hashlib.sha256).hexdigest()
                if not hmac.compare_digest(expected, signature):
                    raise ValueError()
                decoded = json.loads(base64.urlsafe_b64decode(data))
                if decoded["owner"] != str(authority.account_id) or decoded["revision"] != revision:
                    raise ValueError()
                offset = decoded["offset"]
                if type(offset) is not int or not 0 <= offset <= 1000:
                    raise ValueError()
            except (ValueError, KeyError, TypeError):
                raise ResearchError("SNAPSHOT_EXPIRED") from None
        active = [row for row in rows if row["lifecycle"] == "active"]
        selected = active[offset : offset + limit]
        sessions = [
            session_dto(self.repository.read_session(authority, row["id"])) for row in selected
        ]
        if self.repository.session_snapshot(authority)[1] != revision:
            raise ResearchError("SNAPSHOT_EXPIRED")
        next_cursor = None
        if offset + limit < len(active):
            data = base64.urlsafe_b64encode(
                json.dumps(
                    {
                        "owner": str(authority.account_id),
                        "revision": revision,
                        "offset": offset + limit,
                    }
                ).encode()
            ).decode()
            next_cursor = (
                data + "." + hmac.new(self.cursor_key, data.encode(), hashlib.sha256).hexdigest()
            )
        return {
            "sessions": sessions,
            "page": {"snapshotRevision": revision, "nextCursor": next_cursor},
        }

    def delete_sessions(self, authority, value, *, operation=None):
        self.require_policy(value["policy"])
        if value.get("confirmed") is not True:
            raise ResearchError("INVALID_ARGUMENT")
        if value["scope"] not in {"one-session", "all-sessions"} or (
            value["scope"] == "one-session"
        ) != ("sessionId" in value):
            raise ResearchError("INVALID_ARGUMENT")
        return self.repository.delete_selection(authority, value, operation=operation or uuid4())

    def suspended_private(self, authority, value):
        self.repository.run(
            authority, lambda conn: self.repository.context(conn, authority, value["contextId"])
        )
        raise ResearchError("POLICY_UNRESOLVED")

    def accept(self, authority, operation, value, kind):
        self.require_policy(value["policy"])
        if (
            not isinstance(value["text"], str)
            or not value["text"].strip()
            or len(value["text"].encode()) > self.policy.text_bytes
        ):
            raise ResearchError("INVALID_ARGUMENT")
        if kind == "novelty-discussion":
            source = self.jobs.read_artifact(authority, value["source"])
            if source["kind"] != "novelty-result" or source["availability"] != "ready":
                raise ResearchError("SOURCE_INELIGIBLE")
            job = self.jobs.read_job(
                authority, source["job_id"], source["context_id"], "novelty-analysis"
            )
            value = dict(value, scope=job["scope"])
        self.scope(authority, value["scope"])
        if kind == "novelty-analysis":
            if value.get("inputMode") not in {"topic", "manuscript"}:
                raise ResearchError("INVALID_ARGUMENT")
            if value["inputMode"] == "manuscript":
                # UI controls are not the boundary: private processing is suspended.
                raise ResearchError("POLICY_UNRESOLVED")
        if value.get("submittedDraft"):
            raise ResearchError("POLICY_UNRESOLVED")
        if self.execution is None or not self.execution.enabled:
            raise ResearchError("DEPENDENCY_UNAVAILABLE")
        row = self.execution.accept(authority, operation, value, kind)
        return {
            "jobId": str(row["id"]),
            "revision": str(row["revision"]),
            "seq": row["seq"],
            "state": row["state"],
            "requestId": str(operation),
            "acceptedAt": row["accepted_at"].isoformat(),
        }

    def snapshot(self, authority, row):
        result = None
        if row["artifact_id"]:
            artifact = self.repository.run(
                authority,
                lambda conn: conn.execute(
                    "SELECT * FROM research.artifact WHERE id=%s AND owner_id=%s",
                    (row["artifact_id"], authority.account_id),
                ).fetchone(),
            )
            if artifact:
                result = {
                    "resultId": str(artifact["id"]),
                    "revision": str(artifact["revision"]),
                    "contentHash": artifact["content_hash"],
                    "mediaType": "application/json",
                }
        return {
            "jobId": str(row["id"]),
            "kind": row["kind"],
            "ownerId": str(row["owner_id"]),
            "revision": str(row["revision"]),
            "seq": row["seq"],
            "state": row["state"],
            "acceptedAt": row["accepted_at"].isoformat(),
            "progress": {"mode": "indeterminate"},
            "result": result,
            "error": None
            if row["state"] != "failed"
            else {
                "code": row["error_code"] or "DEPENDENCY_UNAVAILABLE",
                "messageKey": "research.failed",
                "requestId": str(row["id"]),
                "retryable": False,
            },
        }

    def read_job(self, authority, value):
        row = self.jobs.read_job(authority, value["jobId"], value["contextId"], value["kind"])
        self.scope(authority, row["scope"])
        return self.snapshot(authority, row)

    def read_turn(self, authority, value):
        session = self.repository.read_session(authority, value["sessionId"])
        row = self.jobs.read_job(authority, value["turnId"], session["context_id"], "research-turn")
        if str(row["session_id"]) != value["sessionId"]:
            raise ResearchError("NOT_FOUND")
        self.scope(authority, row["scope"])
        snapshot = self.snapshot(authority, row)
        result = snapshot["result"]
        return {
            "turnId": str(row["id"]),
            "sessionId": str(row["session_id"]),
            "ownerId": str(row["owner_id"]),
            "revision": str(row["revision"]),
            "inputMode": row["input"]["mode"],
            "committedText": row["input"]["text"],
            "submittedDraft": row["input"].get("submittedDraft"),
            "job": snapshot,
            "artifact": {
                "artifactId": result["resultId"],
                "revision": result["revision"],
                "contentHash": result["contentHash"],
            }
            if result
            else None,
        }

    def read_artifact(self, authority, value):
        row = self.jobs.read_artifact(authority, value["artifact"])
        job = self.repository.run(
            authority,
            lambda conn: conn.execute(
                "SELECT scope FROM research.job WHERE id=%s", (row["job_id"],)
            ).fetchone(),
        )
        self.scope(authority, job["scope"])
        if row["availability"] != "ready":
            return {
                "availability": row["availability"],
                "artifactId": str(row["id"]),
                "reasonKey": "research.artifact." + row["availability"],
            }
        return {"availability": "ready", "prepared": artifact_dto(row)}

    def readNoveltyArtifactForExport(self, authority, reference):
        """Internal C07 read: no export approval or external effect is created."""
        response = self.read_artifact(authority, {"artifact": reference})
        if response["availability"] != "ready" or response["prepared"]["kind"] != "novelty-result":
            raise ResearchError("SOURCE_INELIGIBLE")
        return response
