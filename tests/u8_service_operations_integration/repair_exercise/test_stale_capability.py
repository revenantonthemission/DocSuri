"""The repair exercise's regression test (U8 plan, decision "The repair exercise"; BR1.3,
BR3.2): a stale capability is never available.

The checks run in a clean `git worktree` checkout, where the realm's owned manifest names
another repository, so they need no database: the resolver itself, and the route's
resolution (`u8_routes.resolve_items`) under a request identifier, as a request carries
one. When `DOCSURI_U8_REPAIR_TRACE` names a file (the `repair-exercise` phase), a failing
resolution's request identifier is written there as `failing-request`, beside the log
lines the resolver wrote for it (`navigation.resolved`, with where it decided), so the
phase follows the failing request through the logs to the resolver.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

from backend.local_browser import CURRENT_REQUEST_ID
from backend.u8_registry import NAVIGATION
from backend.u8_routes import NAVIGATION_LOG, RESOLVER, navigation_items, resolve_items

TRACE = "DOCSURI_U8_REPAIR_TRACE"


class Resolutions(logging.Handler):
    """The resolver's log lines, as the realm writes them."""

    def __init__(self):
        super().__init__(logging.INFO)
        self.lines: list[dict] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append({key: getattr(record, key, None)
                           for key in ("requestId", "event", "location", "unavailable")})


@contextmanager
def traced(request_id: str):
    """One request: its identifier in context and the resolver's lines while it runs; on
    a failure, the failing request and those lines go to the phase's trace file."""
    handler = Resolutions()
    NAVIGATION_LOG.addHandler(handler)
    previous = NAVIGATION_LOG.level
    NAVIGATION_LOG.setLevel(logging.INFO)
    token = CURRENT_REQUEST_ID.set(request_id)
    try:
        yield handler
    except AssertionError:
        path = os.environ.get(TRACE)
        if path:
            with open(path, "a", encoding="utf-8") as stream:
                stream.write(json.dumps({"kind": "failing-request",
                                         "requestId": request_id}) + "\n")
                for line in handler.lines:
                    stream.write(json.dumps({"kind": "log", **line}) + "\n")
        raise
    finally:
        CURRENT_REQUEST_ID.reset(token)
        NAVIGATION_LOG.removeHandler(handler)
        NAVIGATION_LOG.setLevel(previous)


def states_with(stale_capability: str) -> dict:
    states = {entry.capability_id: SimpleNamespace(state="available") for entry in NAVIGATION}
    states[stale_capability] = SimpleNamespace(state="stale")
    return states


def test_stale_capability_is_never_available():
    """The resolver itself: a stale capability's entries are disabled with their reason,
    signed in or not, whatever else is available."""
    for stale in {entry.capability_id for entry in NAVIGATION if entry.placement != "footer"}:
        for signed_in in (True, False):
            items = {item["routeId"]: item for item in navigation_items(
                states_with(stale), signed_in=signed_in, administrator=True)}
            for entry in NAVIGATION:
                if entry.capability_id != stale or entry.placement == "footer":
                    continue
                assert items[entry.route_id]["available"] is False, (stale, entry.route_id)
                if signed_in or entry.access == "anonymous":
                    assert items[entry.route_id]["reasonKey"] == "nav.capabilityStale"


def test_a_requests_resolution_disables_a_stale_entry_and_is_logged_with_its_identifier():
    """The route's resolution for one request: the stale export entry is disabled, and
    the resolver's log line carries the request's identifier and where it decided."""
    request_id = str(uuid4())
    with traced(request_id) as resolutions:
        items = {item["routeId"]: item for item in resolve_items(
            states_with("export"), signed_in=True, administrator=False)}
        assert [line["requestId"] for line in resolutions.lines] == [request_id]
        assert resolutions.lines[0]["location"] == RESOLVER == "u8_routes.navigation_items"
        assert (items["export"]["available"], items["export"].get("reasonKey")) == (
            False, "nav.capabilityStale")
        assert "export" in resolutions.lines[0]["unavailable"]
