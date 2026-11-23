"""The consumer inventory (U8 plan Step 31; BR9.11, BR9.14, Workflow 11).

v1 keeps no per-request access records on this Mac, so v1's route use and request rate
come from a Cloudflare request-analytics export you take from the dashboard
(`cloudflare_export`, the person's decision of 2026-10-24, "Cloudflare's numbers"),
read by client where the export names one: the user agent and the route family only.
Nothing else of a row is kept: no address, no query, no identifier inside a path. A
route family keeps a path's first segments and replaces every identifier-like segment
with `{id}`. Known integrations are added. Each consumer then gets the disposition your
decision approves (moves with v2, retired with v1, informed, accepted to break); the
inventory is complete only when every consumer has one, and a complete inventory is a
switch precondition (BR9.2).

The inventory records the export's window, its request count, and v1's busiest interval
(`peakRequests` over `intervalSeconds`): the peak rate the install's performance phase
compares the test's pace against. The counts over time and by route family go to an
owner-only evidence file beside it.

The ledger keeps each client as an opaque reference (`ua:` and the first 16 hex of its
user agent's SHA-256); the user agent's text is shown to you in the decision's subject
only.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
from collections import Counter
from collections.abc import Callable, Iterable
from pathlib import Path
from uuid import uuid4

from backend.modules.operations.errors import OperationsError
from backend.modules.operations.ledger import utc_text

from .cloudflare_export import Export

KIND = "consumer-inventory"
SOURCE = "cloudflare-export"
DISPOSITIONS = ("moves-with-v2", "retired-with-v1", "informed", "accepted-to-break")
STEP = "consumer-disposition"
MAX_SEGMENTS = 3
MAX_ROUTES = 64
_IDENTIFIER = re.compile(
    r"\d+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|"
    r"\d{4}\.\d{4,5}(v\d+)?|[0-9a-f]{16,}", re.IGNORECASE)
_SEGMENT = re.compile(r"[A-Za-z0-9_.-]{1,64}")


def route_family(path: str) -> str | None:
    """A path's family: its first segments, identifiers as `{id}`, no query."""
    bare = path.split("?", 1)[0].split("#", 1)[0]
    if not bare.startswith("/"):
        return None
    segments = [segment for segment in bare.split("/") if segment][:MAX_SEGMENTS]
    family = []
    for segment in segments:
        if _IDENTIFIER.fullmatch(segment):
            family.append("{id}")
        elif _SEGMENT.fullmatch(segment):
            family.append(segment.lower())
        else:
            family.append("{id}")
    return "/" + "/".join(family)


def client_ref(user_agent: str) -> str:
    return "ua:" + hashlib.sha256(user_agent.encode()).hexdigest()[:16]


class ConsumerInventory:
    def __init__(self, ledger, *, window_seconds: int, clock: Callable[[], dt.datetime],
                 evidence: Path | None = None):
        """`window_seconds` is the policy's window, used when no export was observed
        (known integrations only); `evidence` the owner-only folder for the counts."""
        self.ledger, self.window, self.clock = ledger, window_seconds, clock
        self.evidence = evidence
        self.export: Export | None = None

    def observe(self, export: Export) -> list[dict]:
        """The clients the export names: user agent and route families only, with each
        client's request count. Without a user agent the export names no client; its
        counts still make the window, the totals and the peak."""
        self.export = export
        routes: dict[str, set[str]] = {}
        requests: Counter = Counter()
        for row in export.rows:
            if row.agent is None:
                continue
            requests[row.agent] += row.requests
            family = route_family(row.path) if row.path is not None else None
            routes.setdefault(row.agent, set())
            if family is not None:
                routes[row.agent].add(family)
        return [{"clientRef": client_ref(agent), "userAgent": agent,
                 "routesUsed": sorted(routes[agent])[:MAX_ROUTES],
                 "requests": requests[agent]}
                for agent in sorted(routes)]

    def _counts(self) -> dict:
        """The export's counts over time and by route family: the evidence file."""
        export = self.export
        families: Counter = Counter()
        for row in export.rows:
            family = route_family(row.path) if row.path is not None else None
            if family is not None:
                families[family] += row.requests
        return {"intervalSeconds": export.interval_seconds,
                "series": [{"at": utc_text(at), "requests": count}
                           for at, count in export.series()],
                "routes": dict(sorted(families.items()))}

    def _write_evidence(self, inventory_id: str, value: dict) -> None:
        self.evidence.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = self.evidence / f"consumer-inventory-{inventory_id}.json"
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, sort_keys=True)

    def record(self, observed: list[dict], known: Iterable[dict] = ()) -> dict:
        """The inventory, observed clients and known integrations, no disposition yet,
        with the export's window, request count and busiest interval when `observe`
        read one."""
        now = self.clock()
        consumers = [{"clientRef": item["clientRef"], "routesUsed": item["routesUsed"],
                      "source": "observed",
                      **({"requests": item["requests"]} if "requests" in item else {})}
                     for item in observed]
        seen = {item["clientRef"] for item in consumers}
        for item in known:
            if item["clientRef"] not in seen:
                consumers.append({"clientRef": item["clientRef"],
                                  "routesUsed": list(item.get("routesUsed", [])),
                                  "source": "known"})
        inventory_id = str(uuid4())
        if self.export is None:
            start, end = now - dt.timedelta(seconds=self.window), now
        else:
            start, end = self.export.window()
        record = {"inventoryId": inventory_id, "observedFrom": utc_text(start),
                  "observedUntil": utc_text(end), "consumers": consumers,
                  "complete": not consumers}
        if self.export is not None:
            peak_at, peak = self.export.peak()
            record.update(source=SOURCE, requests=self.export.total, peakRequests=peak,
                          peakAt=utc_text(peak_at),
                          intervalSeconds=self.export.interval_seconds)
            if self.evidence is not None:
                self._write_evidence(inventory_id, self._counts())
        self.ledger.append(KIND, record, expect_revision=0)
        return record

    def dispose(self, inventory_id, client: str, disposition: str, approval_id) -> dict:
        """Your decision's disposition for one consumer; the inventory is complete once
        every consumer has one (BR9.11)."""
        if disposition not in DISPOSITIONS:
            raise OperationsError("INVALID_INPUT")

        def step(view):
            current = view.get(KIND, str(inventory_id))
            if current is None:
                raise OperationsError("NOT_FOUND")
            approval = view.get("maintainer-approval", str(approval_id))
            if approval is None or approval["step"] != STEP or approval[
                "decision"
            ] != "approved" or approval["subjectRef"] != client:
                raise OperationsError("FORBIDDEN", current={"reasonKey": "decision-required"})
            if not any(item["clientRef"] == client for item in current["consumers"]):
                raise OperationsError("NOT_FOUND")
            consumers = [
                {**item, "disposition": disposition, "approvalId": approval["approvalId"]}
                if item["clientRef"] == client else item for item in current["consumers"]
            ]
            record = {**current, "consumers": consumers,
                      "complete": all("approvalId" in item for item in consumers)}
            view.append(KIND, record, expect_revision=view.revision(KIND, str(inventory_id)))
            return record

        return self.ledger.atomic(step)
