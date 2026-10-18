"""Owner-scoped topics service: follow/unsubscribe/reactivate, settings saves,
reads and the run-scoped reconciliation resolve.

Every read and write carries the caller's authority; nothing here resolves a
caller-supplied identity. The topic key is normalized once at the boundary —
Unicode NFC, case-folded, whitespace-collapsed — so one spelling maps to one
subscription row (BR1.1). Payloads are shaped for the browser surface; the
resolve action requires the human decision to name its assumption (BR3.2).
"""

import datetime as dt
import unicodedata

from backend.transactions import Authority

from .errors import TopicsError
from .repository import TopicsRepository

DECISIONS = {"delivered": "sent", "not-delivered": "failed"}


def normalize_topic_key(value):
    if not isinstance(value, str):
        raise TopicsError("INVALID_ARGUMENT", current={"field": "topicKey"})
    key = " ".join(unicodedata.normalize("NFC", value).casefold().split())
    if not 1 <= len(key.encode()) <= 160:
        raise TopicsError("INVALID_ARGUMENT", current={"field": "topicKey"})
    return key


def _display_name(value):
    if not isinstance(value, str) or not 1 <= len(value.strip().encode()) <= 160:
        raise TopicsError("INVALID_ARGUMENT", current={"field": "displayName"})
    return value.strip()


def parse_delivery_time(value):
    if not isinstance(value, str):
        raise TopicsError("INVALID_ARGUMENT", current={"field": "deliveryTimeLocal"})
    try:
        parsed = dt.time.fromisoformat(value)
    except ValueError as error:
        raise TopicsError("INVALID_ARGUMENT", current={"field": "deliveryTimeLocal"}) from error
    if parsed.second or parsed.tzinfo is not None:
        raise TopicsError("INVALID_ARGUMENT", current={"field": "deliveryTimeLocal"})
    return parsed


def _time_text(value):
    return value.isoformat(timespec="minutes") if value is not None else None


def _iso(value):
    return value.isoformat() if value is not None else None


def _settings_payload(row):
    if row is None:
        return None
    return {
        "cadence": row["cadence"],
        "deliveryTimeLocal": _time_text(row["delivery_time_local"]),
        "deliveryDay": row["delivery_day"],
        "contentWindowDays": row["content_window_days"],
        "revision": row["revision"],
    }


def _run_payload(row):
    outcome = None
    if row.get("observed_state") is not None:
        outcome = {
            "observedState": row["observed_state"],
            "observedAt": _iso(row.get("observed_at")),
            "reconciledState": row.get("reconciled_state"),
            "reconciledAt": _iso(row.get("reconciled_at")),
            "failureReason": row.get("failure_reason"),
        }
    send_log = None
    if row.get("path_kind") is not None:
        send_log = {
            "pathKind": row["path_kind"],
            "transportReceipt": row.get("transport_receipt"),
            "acknowledgedAt": _iso(row.get("acknowledged_at")),
        }
    return {
        "runId": str(row["id"]),
        "topicId": str(row["topic_id"]),
        "windowStart": row["window_start"].isoformat(),
        "windowEnd": row["window_end"].isoformat(),
        "state": row["state"],
        "settingsRevision": row["settings_revision"],
        "digestContent": row["digest_content"],
        "createdAt": _iso(row["created_at"]),
        "outcome": outcome,
        "sendLog": send_log,
        "preferenceSnapshot": row.get("preference_snapshot"),
        "presentation": row.get("presentation"),
    }


class TopicsService:
    def __init__(self, transactions):
        self.repository = TopicsRepository(transactions)

    def follow(self, authority: Authority, topic_key, display_name):
        key = normalize_topic_key(topic_key)
        name = _display_name(display_name)
        result = self.repository.follow(authority, key, name)
        return {
            "topicId": str(result["topic"]["id"]),
            "status": result["topic"]["status"],
            "reactivated": result["reactivated"],
        }

    def list_topics(self, authority: Authority):
        return [
            {
                "topicId": str(row["id"]),
                "topicKey": row["topic_key"],
                "displayName": row["display_name"],
                "status": row["status"],
                "followedAt": _iso(row["followed_at"]),
                "settings": _settings_payload(
                    {
                        "cadence": row["cadence"],
                        "delivery_time_local": row["delivery_time_local"],
                        "delivery_day": row["delivery_day"],
                        "content_window_days": row["content_window_days"],
                        "revision": row["settings_revision"],
                    }
                ),
                "lastRun": {
                    "runId": str(row["last_run_id"]) if row["last_run_id"] is not None else None,
                    "state": row["last_run_state"],
                    "windowEnd": row["last_run_window_end"].isoformat()
                    if row["last_run_window_end"] is not None
                    else None,
                    "observedState": row["last_outcome_state"],
                },
            }
            for row in self.repository.list_topics(authority, 50)
        ]

    def read_topic(self, authority: Authority, topic_id):
        view = self.repository.read_topic(authority, topic_id)
        return {
            "topicId": str(view["topic"]["id"]),
            "topicKey": view["topic"]["topic_key"],
            "displayName": view["topic"]["display_name"],
            "status": view["topic"]["status"],
            "followedAt": _iso(view["topic"]["followed_at"]),
            "settings": _settings_payload(view["settings"]),
            "runs": [_run_payload(row) for row in view["runs"]],
            "effectivePreferences": view["effectivePreferences"],
        }

    def read_run(self, authority: Authority, topic_id, run_id):
        return _run_payload(self.repository.read_run(authority, topic_id, run_id))

    def save_settings(self, authority: Authority, topic_id, body):
        if not isinstance(body, dict):
            raise TopicsError("INVALID_ARGUMENT")
        expected = body.get("revision")
        if type(expected) is not int:
            raise TopicsError("INVALID_ARGUMENT", current={"field": "revision"})
        result = self.repository.save_settings(
            authority,
            topic_id,
            expected,
            body.get("cadence"),
            parse_delivery_time(body.get("deliveryTimeLocal")),
            body.get("deliveryDay"),
            body.get("contentWindowDays"),
        )
        return {
            "settings": _settings_payload(result["settings"]),
            "discardedRunIds": [str(row) for row in result["discarded"]],
            "unchanged": result["unchanged"],
        }

    def unsubscribe(self, authority: Authority, topic_id):
        result = self.repository.unsubscribe(authority, topic_id)
        return {
            "topicId": str(result["topic"]["id"]),
            "status": result["topic"]["status"],
            "discardedRunIds": [str(row) for row in result["discarded"]],
            "unchanged": result["unchanged"],
        }

    def resolve(self, authority: Authority, topic_id, run_id, body):
        """The owner's explicit resolution; the body names the assumption (BR3.2)."""
        if not isinstance(body, dict):
            raise TopicsError("INVALID_ARGUMENT")
        decision = body.get("decision")
        assumption = body.get("assumption")
        if decision not in DECISIONS:
            raise TopicsError("INVALID_ARGUMENT", current={"field": "decision"})
        if not isinstance(assumption, str) or not assumption.strip():
            raise TopicsError("INVALID_ARGUMENT", current={"field": "assumption"})
        if len(assumption.encode()) > 200:
            raise TopicsError("INVALID_ARGUMENT", current={"field": "assumption"})
        run = self.repository.resolve_run(authority, topic_id, run_id, DECISIONS[decision])
        return {
            "runId": str(run["id"]),
            "state": run["state"],
            "decision": decision,
            "assumption": assumption.strip(),
        }
