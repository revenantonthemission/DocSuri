"""Trusted optional activity relay; capture boundaries before the source action.

The acknowledged source operation is authoritative. Activity has no durable
acceptance receipt at the browser boundary: a failed relay is unavailable, never
reported as recorded. Recovery reads never replay a source operation.
"""

from datetime import UTC, datetime
from uuid import uuid5

import psycopg

from backend.transactions import Busy


class ActivityRelay:
    def __init__(self, service, producer):
        service._producer(producer)
        self.service, self.producer = service, producer

    def capture(self, authority, operation, paper, activity):
        try:
            revision, consent, boundary = self.service.transactions.run(
                "personalization", lambda conn: self.service._state(conn, authority)
            )
        except (Busy, psycopg.OperationalError, psycopg.InterfaceError):
            return None
        if not consent["granted"]:
            return None
        return {
            "eventId": str(uuid5(operation, self.producer.component + ":" + activity)),
            "accountId": str(authority.account_id),
            "paper": paper,
            "activityId": activity,
            "occurredAt": datetime.now(UTC).isoformat(),
            "authorityRevision": str(revision),
            "consentRevision": str(consent["revision"]),
            "inputBoundary": str(boundary),
        }

    def deliver(self, authority, event):
        if event is None:
            return {"disposition": "not-captured"}
        try:
            return self.service.record_behavior(self.producer, authority, event)
        except (Busy, psycopg.OperationalError, psycopg.InterfaceError):
            return {"disposition": "unavailable"}
        except ValueError:
            # An already recorded event retains its first evidence. Browser
            # retries can have a different observation time but never overwrite it.
            return {"disposition": "conflict"}
        except PermissionError:
            # Withdrawal between a source read/save and this optional relay
            # must suppress tracking, not erase the acknowledged primary write.
            return {"disposition": "source-unavailable"}
