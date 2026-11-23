"""The owner job list's cursor and item mapping (U8 plan Step 7; A2, common rule 6).

A page is read newest first on `research.job(owner_id, accepted_at DESC, id)`. The
cursor is opaque: an HMAC-SHA256-signed token binding the owner and kind (as a keyed
scope, so no identifier is readable), the schema form, the snapshot (the newest
`accepted_at` the first page saw, so later pages never shift as new jobs arrive), the
keyset position and an expiry. An altered, foreign or expired token is refused.
"""

from __future__ import annotations

import base64
import binascii
import datetime as dt
import hashlib
import hmac
import json
from collections.abc import Callable
from uuid import UUID

FORM = "u8-job-list-v1"
KINDS = {"research": ("research-turn",), "novelty": ("novelty-analysis", "novelty-discussion")}
KIND_OF = {job: kind for kind, jobs in KINDS.items() for job in jobs}
STATES = ("accepted", "running", "cancel_requested", "succeeded", "failed", "cancelled")
LABELS = {"novelty-analysis": "참신성 분석", "novelty-discussion": "참신성 토론"}
MAX_LABEL = 200
MAX_TOKEN = 512
LIFETIME_SECONDS = 300


class JobListCursorInvalid(ValueError):
    """A cursor that is altered, foreign, of another kind or expired."""


def utc_text(moment: dt.datetime) -> str:
    return moment.astimezone(dt.UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_time(value: str) -> dt.datetime:
    moment = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        raise ValueError("cursor time must be aware")
    return moment


class JobListCursor:
    def __init__(
        self, key: bytes, *, clock: Callable[[], dt.datetime],
        lifetime_seconds: int = LIFETIME_SECONDS,
    ):
        if not isinstance(key, bytes) or len(key) != 32:
            raise ValueError("a 32-byte cursor key is required")
        if type(lifetime_seconds) is not int or not 1 <= lifetime_seconds <= LIFETIME_SECONDS:
            raise ValueError("cursor lifetime outside its bound")
        self.key, self.clock, self.lifetime = key, clock, lifetime_seconds

    def _scope(self, owner: UUID, kind: str | None) -> str:
        return hmac.digest(self.key, f"{FORM}:{owner}:{kind or '*'}".encode(), "sha256").hex()

    def encode(
        self, owner: UUID, kind: str | None, snapshot: dt.datetime,
        accepted_at: dt.datetime, job_id: UUID,
    ) -> str:
        raw = json.dumps(
            {
                "form": FORM,
                "scope": self._scope(owner, kind),
                "snapshot": utc_text(snapshot),
                "after": [utc_text(accepted_at), str(job_id)],
                "expires": int(self.clock().timestamp()) + self.lifetime,
            },
            sort_keys=True, separators=(",", ":"),
        ).encode()
        token = base64.urlsafe_b64encode(raw + hmac.digest(self.key, raw, "sha256")).decode()
        if len(token) > MAX_TOKEN:
            raise ValueError("cursor exceeds its bound")
        return token.rstrip("=")

    def decode(self, owner: UUID, kind: str | None, token: str) -> dict:
        if not isinstance(token, str) or not 1 <= len(token) <= MAX_TOKEN:
            raise JobListCursorInvalid("cursor outside its bound")
        try:
            value = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
            raw, signature = value[:-32], value[-32:]
            if len(signature) != 32 or not hmac.compare_digest(
                signature, hmac.digest(self.key, raw, "sha256")
            ):
                raise JobListCursorInvalid("cursor signature differs")
            parsed = json.loads(raw)
            if (
                parsed["form"] != FORM
                or parsed["scope"] != self._scope(owner, kind)
                or parsed["expires"] <= self.clock().timestamp()
            ):
                raise JobListCursorInvalid("stale or foreign cursor")
            return {
                "snapshot": parse_time(parsed["snapshot"]),
                "acceptedAt": parse_time(parsed["after"][0]),
                "jobId": UUID(parsed["after"][1]),
            }
        except JobListCursorInvalid:
            raise
        except (KeyError, TypeError, IndexError, ValueError, binascii.Error) as error:
            raise JobListCursorInvalid("invalid cursor") from error


def label_of(row: dict) -> str:
    """A research turn is labelled by its session's title, a novelty job by its kind."""
    if row["kind"] == "research-turn" and row.get("session_title"):
        text = " ".join(row["session_title"].split())
        return text[:MAX_LABEL] or "연구"
    return LABELS.get(row["kind"], "연구")


def item_of(row: dict, now: dt.datetime) -> dict:
    """A2's `ResearchJobListItem`."""
    if row["state"] not in STATES:
        raise ValueError("job state outside A2's vocabulary")
    available = (
        row["state"] == "succeeded"
        and row.get("artifact_availability") == "ready"
        and row.get("artifact_expires_at") is not None
        and row["artifact_expires_at"] > now
    )
    return {
        "jobId": str(row["id"]),
        "kind": KIND_OF[row["kind"]],
        "label": label_of(row),
        "state": row["state"],
        "createdAt": utc_text(row["accepted_at"]),
        "updatedAt": utc_text(row["updated_at"]),
        "resultAvailable": bool(available),
    }


def page_digest(items: list[dict]) -> str:
    return hashlib.sha256(
        json.dumps(items, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
