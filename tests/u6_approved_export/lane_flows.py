"""Lane and pass flows: the real `ExportLane` and `ExportPass` over the realm, the real
SDK over the fake Notion, the research-port double for U4 and the injected clock.

The lane is driven item by item through `run_item` in component tests, so nothing waits
on a thread; the integration tests start its thread. Policies are smaller than
production where time matters, and the clock is advanced instead of waiting.
"""

import threading
import time
from dataclasses import dataclass
from uuid import UUID

from backend.modules.export.lane import ExportLane, LaneItem
from backend.modules.export.repository import ExportRepository
from backend.modules.export.worker import ExportPass

from tests.u6_approved_export import notion_flows as nf
from tests.u6_approved_export import service_flows as sf
from tests.u6_approved_export import store_flows as flows

# The largest due batch the store answers; a test's own rows must lie within it.
DUE_LIMIT = 100
MAX_DRAIN_PASSES = 100


@dataclass
class LaneRig:
    rig: sf.Rig
    lane: ExportLane
    step: ExportPass

    @property
    def fake(self):
        return self.rig.fake

    @property
    def clock(self):
        return self.rig.clock

    @property
    def repo(self):
        return self.rig.repo


class LaneDouble:
    """Stands in for the lane in pass tests: records the items offered to it."""

    def __init__(self, *, idle: bool = True):
        self.idle = idle
        self.offered: list[LaneItem] = []

    def offer(self, item: LaneItem) -> bool:
        self.offered.append(item)
        return True


class OwnDue:
    """The real store, with `due_items` kept to this test's effects in the order the
    store returned them. The realm persists across phases, and the database and
    repository layers leave due rows of synthetic owners that have no account, so no
    erase ticket can clear them."""

    def __init__(self, repository, effect_ids):
        self._repository = repository
        self._ids = set(effect_ids)

    def due_items(self, now, limit=None):
        rows = self._repository.due_items(now, limit=DUE_LIMIT)
        return [row for row in rows if row["id"] in self._ids][:limit]

    def __getattr__(self, name):
        return getattr(self._repository, name)


def own_step(lr: "LaneRig", lane, effect_ids, repository=None) -> ExportPass:
    """A pass step over the real store whose hand-over sees only this test's effects."""
    store = repository or OwnDue(lr.repo, effect_ids)
    return ExportPass(store, lr.rig.research, lane, policy=lr.rig.policy, clock=lr.clock)


def drain(transactions, lr: "LaneRig") -> None:
    """Real passes with the default batch until nothing more is invalidated, trimmed or
    purged anywhere in the realm, so a test's housekeeping counts are its own."""
    policy = nf.policy()
    step = ExportPass(
        ExportRepository(transactions, policy),
        lr.rig.research,
        LaneDouble(idle=False),
        policy=policy,
        clock=lr.clock,
    )
    keys = ("sessionInvalidated", "sourceInvalidated", "trimmed", "purged")
    for _ in range(MAX_DRAIN_PASSES):
        if not any(step.run_once()[key] for key in keys):
            return
    raise AssertionError("the realm did not drain")


def wait_for(condition, *, seconds: float = 20.0, interval: float = 0.05):
    """Poll a condition until it holds; deterministic, bounded, never a fixed sleep."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = condition()
        if value:
            return value
        time.sleep(interval)
    raise AssertionError("condition not reached in time")


def build(transactions, connect, authority, tmp_path, *, lane=None, **options) -> LaneRig:
    rig = sf.build(transactions, connect, authority, tmp_path, **options)
    real = ExportLane(
        rig.repo, rig.service.adapter, rig.service.binding, policy=rig.policy, clock=rig.clock
    )
    step = ExportPass(
        rig.repo, rig.research, lane or real, policy=rig.policy, clock=rig.clock
    )
    return LaneRig(rig, real, step)


def pressed(
    lr: LaneRig, *, page: str | None = None, source: dict | None = None, configure: bool = True
) -> dict:
    """One pressed export (connecting the owner first unless asked not to): the effect
    is accepted, nothing is written."""
    if configure:
        lr.rig.configure()
    page = page or lr.rig.page()
    flow = lr.rig.press(page, source)
    flow["page"] = page
    return flow


def item(effect: dict, kind: str = "execute") -> LaneItem:
    """The lane item for an effect, from its wire form or its store row."""
    if "effectId" in effect:
        return LaneItem(kind, UUID(effect["effectId"]), int(effect["revision"]))
    return LaneItem(kind, effect["id"], effect["revision"])


def effect_id(effect: dict) -> UUID:
    return UUID(effect["effectId"]) if "effectId" in effect else effect["id"]


def row(connect, effect: dict) -> dict:
    return flows.effect_row(connect, effect_id(effect))


def attempts(connect, effect: dict) -> list:
    with connect("export") as conn:
        return conn.execute(
            "SELECT attempt_number,started_at,deadline_at,ended_at,response_class,"
            "provider_request_id,creator_confirmed,writer_identity,connection_revision "
            "FROM export.attempt WHERE effect_id=%s ORDER BY attempt_number",
            (effect_id(effect),),
        ).fetchall()


def checks(connect, effect: dict) -> list:
    with connect("export") as conn:
        return conn.execute(
            "SELECT result,checked_at,remote_reference,other_marked_pages,evidence_hash "
            "FROM export.reconciliation_check WHERE effect_id=%s ORDER BY checked_at,id",
            (effect_id(effect),),
        ).fetchall()


def connection(connect, rig: sf.Rig) -> dict:
    return flows.connection_row(connect, UUID(rig.connection()["connectionId"]))


def on_write(fake, callback) -> None:
    """Run `callback` in its own thread while the fake answers a create, and wait for it
    there: the lane's write is in flight and must hold no transaction (D8)."""
    original = fake.handle_async_request

    async def handle(request):
        if request.method == "POST" and request.url.path == "/v1/pages":
            failures: list = []

            def run():
                try:
                    callback()
                except BaseException as error:  # noqa: BLE001 - surfaced to the test below
                    failures.append(error)

            worker = threading.Thread(target=run)
            worker.start()
            worker.join(30)
            if failures:
                raise AssertionError("the in-flight callback failed") from failures[0]
        return await original(request)

    fake.handle_async_request = handle


def latest_lane_status(connect) -> dict | None:
    with connect("export") as conn:
        return conn.execute("SELECT outcome,observed_at FROM export.lane_status").fetchone()
