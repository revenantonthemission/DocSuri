"""C11 `readDashboard` and `listIncidents` (U8 plan Step 39; A5, BR3.8, observability-design
§ 4).

The dashboard answers C11's frozen `OpsDashboardPage`: a page of `OpsDashboardItem`s. Each
part of observability-design § 4's contents is one or more items, told apart by the
item's `capability`:

- every capability of the registry, by its own id: its derived state (BR3.2), its age and
  freshness (A5), its reason and limitation keys, and its error rate over the window
  (`error-rate-permille:<n>`). A stale capability answers status `unknown` with freshness
  `stale`: stale is derived at read time and never stored;
- `operations.backup-set`: the backup sets of this environment, newest first, each with
  its integrity as the status, its database incarnation as the component and its
  retention (`retain-until:<time>`), trigger and ledger revision (`revision:<n>`, the
  expected revision a restore request names) as limitations;
- `operations.backup-revision`: the environment's backup revision (`revision:<n>`), the
  expected revision a `backup.create` request names (BR4.9);
- `operations.restore-verification`: the latest verifications, with their result;
- `operations.recovery-request`: the active and the most recent recovery requests, the
  request id as the evidence reference and `state:`, `operation:`, `origin:` and
  `environment:` limitations;
- `operations.email-allowance`: the UTC day's and month's counts (`daily:<n>`,
  `monthly:<n>`), a measured zero shown as `daily:0`;
- `operations.latency`: the newest latency summary of each route class (`p95-ms:<n>`,
  `count:<n>`, `errors-5xx:<n>`), or `p95-ms:unknown` while the class has no requests;
  a class whose newest window has requests also carries that window's share of 5xx
  answers (`error-rate-permille:<n>`, U8 plan Step 60(c));
- `operations.availability`: the month's figure (`availability-permille:<n>`,
  `budget-left-seconds:<n>`), present once the availability record has a line, counted
  in the policy's slots and from admission opening in its first month (Step 60(a),
  L1-45).

U8 plan Step 60 adds:

- `operations.standing-job`: the standing job's last run, the newest availability line
  of this or the previous Seoul month (`observedAt`, `ageSeconds`), late
  (`standing-job-late`) past two of the policy's slots, with its own scheduled runs'
  failures over the policy's window (`failed-backups:<n>`, `failed-verifications:<n>`,
  `failed-disposals:<n>`); unknown with `standing-job-unrecorded` while no line exists
  (NFR9.7, L1-41);
- each verification also carries `restore-bound-seconds:<n>`, and its HNSW rebuild time
  and 8 GiB projection when recorded (`hnsw-rebuild-seconds:<n>`,
  `hnsw-projected-seconds:<n>`, `hnsw-projection-past-bound`);
- `operations.isolation-result`: the newest isolation result's stop records
  (`stop:<label>:<expiresAt>`), unknown with `isolation-result-unreadable` when the
  newest file cannot be read;
- `operations.lane`: one item per lane, the lane as its component, with its failed and
  terminal jobs over 24 hours (`failed:<n>`, `terminal:<n>`), unknown with
  `lane-count-unavailable` when its read failed (L1-41);
- a capability whose producer dropped observations carries `missing-observations:<n>`
  (NFR9.2).

One failing source gives its own item unknown; every other item still shows.

The items hold identifiers, states, times, reason keys and counts only: never private
text, a credential, an address or a title (BR3.4). The page is stable for its snapshot:
the cursor names the snapshot it was cut from, and a different snapshot answers CONFLICT.

The incident list reads the operations ledger, unresolved first (BR3.7). C11's
`OpsIncidentRead` has no field for the incident's opening time, its diagnosis or its
recovery requests, so they travel as prefixed evidence references (`opened:<time>`,
`role:<abort|rollback-copy|ordinary>`, `diagnosis:<key>`, `recovery:<id>`), beside the
incident's own references.

The two pages' bounds (L1-63): `list-incidents` answers at most 50 incidents a page
(`INCIDENT_LIMIT`, performance-design § 2.3's bound for lists), and `read-dashboard`
keeps one page of up to 200 (`MAX_LIMIT`), one composite read of observability-design
§ 4's contents. A limit above a read's bound is clamped to it, never refused, and a page
without a limit answers 50.
"""

from __future__ import annotations

import base64
import binascii
import datetime as dt
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from backend.u8_policy import PRODUCTION_OPERATIONS, ROUTE_CLASSES
from backend.u8_registry import CAPABILITY_BY_ID

from .errors import OperationsError
from .ledger import utc_text
from .retained_copies import CLOSED

DEFAULT_LIMIT, MAX_LIMIT = 50, 200
# `list-incidents`' page: performance-design § 2.3's 50 rows for lists (L1-63).
INCIDENT_LIMIT = 50
BACKUP_ITEMS, VERIFICATION_ITEMS, REQUEST_ITEMS = 20, 5, 20
BACKUP = "operations.backup-set"
BACKUP_REVISION = "operations.backup-revision"
VERIFICATION = "operations.restore-verification"
REQUEST = "operations.recovery-request"
ALLOWANCE = "operations.email-allowance"
LATENCY = "operations.latency"
AVAILABILITY = "operations.availability"
STANDING_JOB = "operations.standing-job"
ISOLATION_RESULT = "operations.isolation-result"
LANE = "operations.lane"
# The standing job's own runs (Step 60(b)): requests with this origin that ended so.
SCHEDULED_ORIGIN = "schedule"
FAILED_ENDINGS = frozenset({"failed", "refused", "expired"})
# A closed record: nothing is left to dispose of. The one rule platform.status's count
# also follows (retained_copies.CLOSED).
CLOSED_FIELDS = CLOSED
ISOLATION_READ_BYTES = 65536
STATUS_OF_STATE = {"available": "available", "degraded": "degraded",
                   "unavailable": "unavailable", "unknown": "unknown", "stale": "unknown"}
STATUS_OF_INTEGRITY = {"passed": "available", "failed": "unavailable", "unchecked": "unknown"}
STATUS_OF_REQUEST = {
    "succeeded": "available", "failed": "unavailable", "refused": "unavailable",
    "expired": "unavailable", "cancelled": "unavailable", "unknown": "unknown",
}
MAX_ID = 128


def _id(value: str) -> str:
    """A value within C11's identifier bound, kept whole when it fits."""
    return value if len(value) <= MAX_ID else value[:MAX_ID]


def _parse(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(str(text).replace("Z", "+00:00"))


def _digest(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()[:32]


def _item(*, key: str, capability: str, component: str, observed_at: dt.datetime | str,
          status: str, evidence: str, limitations=(), freshness: str | None = None,
          age: int | None = None) -> dict:
    observed = observed_at if isinstance(observed_at, str) else utc_text(observed_at)
    value = {
        "observationId": str(uuid5(NAMESPACE_URL, f"docsuri:ops:{key}")),
        "capability": capability,
        "component": component,
        "observedAt": observed,
        "status": status,
        "evidenceRef": _id(evidence),
        "limitations": [_id(item) for item in limitations if item],
    }
    if freshness is not None:
        value["freshness"] = freshness
    if age is not None:
        value["ageSeconds"] = max(0, int(age))
    value["revision"] = _digest(value)
    return value


def _cursor(snapshot: str, offset: int) -> str:
    raw = json.dumps({"s": snapshot, "o": offset}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _offset(cursor: str | None, snapshot: str) -> int:
    if cursor is None:
        return 0
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        value = json.loads(base64.urlsafe_b64decode(padded.encode()))
    except (ValueError, binascii.Error, UnicodeDecodeError):
        raise OperationsError("INVALID_INPUT") from None
    if not isinstance(value, dict) or set(value) != {"s", "o"} or type(value["o"]) is not int:
        raise OperationsError("INVALID_INPUT")
    if value["s"] != snapshot:
        raise OperationsError("CONFLICT", current={"reasonKey": "snapshot-changed"})
    if value["o"] < 0:
        raise OperationsError("INVALID_INPUT")
    return value["o"]


# Derived at read time (A5), so never part of a snapshot's identity.
READ_TIME_FIELDS = frozenset({"ageSeconds", "freshness", "observedAt", "revision"})


def _snapshot(items: list[dict]) -> str:
    return _digest([{key: value for key, value in item.items() if key not in READ_TIME_FIELDS}
                    for item in items])


def page_of(items: list[dict], page: dict, capability: str | None = None, *,
            maximum: int = MAX_LIMIT) -> dict:
    """One page of `items`, stable for its snapshot (C11 readDashboard semantics): the
    snapshot is what the items say, not when they were read. A limit above the read's
    `maximum` answers at most that many items and is never refused (L1-63)."""
    chosen = [item for item in items if capability is None or item.get("capability") == capability]
    snapshot = _snapshot(chosen)
    limit = page.get("limit") or DEFAULT_LIMIT
    if type(limit) is not int or not 1 <= limit:
        raise OperationsError("INVALID_INPUT")
    limit = min(limit, maximum)
    start = _offset(page.get("cursor"), snapshot)
    window = chosen[start:start + limit]
    following = start + limit
    return {
        "items": window,
        "page": {"nextCursor": _cursor(snapshot, following) if following < len(chosen) else None,
                 "snapshotRevision": snapshot},
    }


class Dashboard:
    """observability-design § 4's contents for one environment, as C11 items."""

    def __init__(self, readiness, ledger, *, environment: str, clock: Callable[[], dt.datetime],
                 allowance=None, latency_folder: Path | None = None,
                 availability_folder: Path | None = None, policy=PRODUCTION_OPERATIONS,
                 isolation_folder: Path | None = None, lane_counts=None):
        self.readiness, self.ledger, self.environment = readiness, ledger, environment
        self.clock, self.allowance = clock, allowance
        self.latency_folder, self.availability_folder = latency_folder, availability_folder
        # Step 60: the operations policy (its slot length, window and bounds), the
        # isolation evidence folder and the lanes' count reader (`LaneCounts`).
        self.policy = policy
        self.isolation_folder, self.lane_counts = isolation_folder, lane_counts

    # --- the items ---------------------------------------------------------------------

    def items(self) -> list[dict]:
        now = self.clock()
        return [
            *self._capabilities(now), *self._backups(), *self._verifications(),
            *self._requests(), *self._allowance(now), *self._latency(now),
            *self._availability(now), *self._standing_job(now), *self._isolation(),
            *self._lanes(now),
        ]

    def _capabilities(self, now: dt.datetime) -> list[dict]:
        items = []
        for name, state in sorted(self.readiness.states().items()):
            registered = CAPABILITY_BY_ID.get(name)
            limitations = [state.reason, *state.limitations]
            if state.total_count:
                limitations.append(
                    f"error-rate-permille:{state.error_count * 1000 // state.total_count}")
            # Step 60(f) (NFR9.2): the producer's observations the store could not keep.
            dropped = getattr(state, "dropped_count", 0) or 0
            if dropped > 0:
                limitations.append(f"missing-observations:{dropped}")
            items.append(_item(
                key=f"capability:{name}:{state.observed_at}", capability=name,
                component=registered.owner if registered else "ServiceOperations",
                observed_at=state.observed_at or now, status=STATUS_OF_STATE[state.state],
                evidence=f"observation:{name}", limitations=limitations,
                freshness=None if state.observed_at is None else (
                    "stale" if state.state == "stale" else "current"),
                age=state.age_seconds,
            ))
        return items

    def _records(self, kind: str) -> list[dict]:
        return [record for record in self.ledger.records(kind)
                if record.get("environment") == self.environment]

    def _backups(self) -> list[dict]:
        """The environment's sets, each with the ledger revision a restore request names
        as its expected revision (BR4.9), then one `operations.backup-revision` item: the
        environment's backup revision, which a `backup.create` request names."""
        records = self._records("backup-set")
        sets = sorted(records, key=lambda r: r["takenAt"], reverse=True)
        items = []
        for record in sets[:BACKUP_ITEMS]:
            if record.get("disposedAt") or record.get("retiredWithVolumeAt"):
                continue
            items.append(_item(
                key=f"backup:{record['backupId']}:{record.get('integrity')}", capability=BACKUP,
                component=_id(str(record["databaseIncarnation"])), observed_at=record["takenAt"],
                status=STATUS_OF_INTEGRITY.get(record.get("integrity"), "unknown"),
                evidence=record["backupId"],
                limitations=[f"trigger:{record['trigger']}",
                             f"retain-until:{record['retainUntil']}",
                             f"revision:{self.ledger.revision('backup-set', record['backupId'])}"],
            ))
        latest = sets[0]["takenAt"] if sets else None
        items.append(_item(
            key=f"backup-revision:{len(records)}", capability=BACKUP_REVISION,
            component="ServiceOperations", observed_at=latest or self.clock(),
            status="available", evidence=f"backup-revision:{self.environment}",
            limitations=[f"revision:{len(records)}"],
        ))
        return items

    def _verifications(self) -> list[dict]:
        found = sorted(self._records("restore-verification"), key=lambda r: r["startedAt"],
                       reverse=True)
        return [
            _item(
                key=f"verification:{record['verificationId']}:{record.get('result')}",
                capability=VERIFICATION, component="ServiceOperations",
                observed_at=record.get("finishedAt") or record["startedAt"],
                status={"verified": "available", "failed": "unavailable"}.get(
                    record.get("result"), "unknown"),
                evidence=record["verificationId"],
                limitations=[f"backup:{record['backupId']}",
                             f"register-head:{record['registerHeadSequence']}",
                             *self._restore_times(record)],
            )
            for record in found[:VERIFICATION_ITEMS]
        ]

    def _restore_times(self, record: dict) -> list[str]:
        """The restore bound, and the HNSW rebuild time with its 8 GiB projection when the
        verification recorded them (Step 60(d)); a set of 0 bytes has no projection and is
        never past the bound."""
        bound = int(self.policy.restore_recreate_and_restore_seconds)
        times = [f"restore-bound-seconds:{bound}"]
        if record.get("hnswRebuildSeconds") is not None:
            times.append(f"hnsw-rebuild-seconds:{int(record['hnswRebuildSeconds'])}")
        projected = record.get("hnswProjectedSeconds")
        if projected is not None:
            times.append(f"hnsw-projected-seconds:{int(projected)}")
            if int(projected) > bound:
                times.append("hnsw-projection-past-bound")
        return times

    def _requests(self) -> list[dict]:
        records = sorted(self._records("recovery-request"), key=lambda r: r["updatedAt"],
                         reverse=True)
        return [
            _item(
                key=f"request:{record['recoveryRequestId']}:{record['revision']}",
                capability=REQUEST, component="ServiceOperations",
                observed_at=record["updatedAt"],
                status=STATUS_OF_REQUEST.get(record["state"], "degraded"),
                evidence=record["recoveryRequestId"],
                limitations=[f"state:{record['state']}", f"operation:{record['operation']}",
                             f"origin:{record['origin']}",
                             f"environment:{record['environment']}",
                             f"target:{record['targetId']}"],
            )
            for record in records[:REQUEST_ITEMS]
        ]

    def _allowance(self, now: dt.datetime) -> list[dict]:
        if self.allowance is None:
            return []
        counts = self.allowance.counts()
        return [_item(
            key=f"allowance:{counts['day']}:{counts['daily']}:{counts['monthly']}",
            capability=ALLOWANCE, component="ServiceOperations", observed_at=now,
            status="available", evidence=f"allowance:{counts['month']}",
            limitations=[f"daily:{counts['daily']}", f"monthly:{counts['monthly']}"],
        )]

    def _latency(self, now: dt.datetime) -> list[dict]:
        if self.latency_folder is None:
            return []
        path = self.latency_folder / f"{now.astimezone(dt.UTC):%Y-%m-%d}.jsonl"
        latest: dict[str, dict] = {}
        if path.is_file() and not path.is_symlink():
            for line in path.read_text().splitlines()[-200:]:
                try:
                    value = json.loads(line)
                except ValueError:
                    continue
                if value.get("class") in ROUTE_CLASSES:
                    latest[value["class"]] = value
        items = []
        for route_class, value in sorted(latest.items()):
            p95 = value.get("p95Ms")
            count, errors = int(value.get("count", 0)), int(value.get("errors5xx", 0))
            # Step 60(c): the newest window's share of 5xx answers; an idle class has none.
            rate = [f"error-rate-permille:{errors * 1000 // count}"] if count > 0 else []
            items.append(_item(
                key=f"latency:{route_class}:{value.get('window')}", capability=LATENCY,
                component=route_class, observed_at=str(value.get("window") or utc_text(now)),
                status="available" if not value.get("errors5xx") else "degraded",
                evidence=f"latency:{route_class}",
                limitations=[f"p95-ms:{'unknown' if p95 is None else int(p95)}",
                             f"count:{count}", f"errors-5xx:{errors}", *rate],
            ))
        return items

    def _availability(self, now: dt.datetime) -> list[dict]:
        if self.availability_folder is None:
            return []
        from docsuri_ops.standing.availability import month_of

        record = self._availability_record()
        month = month_of(now)
        try:
            if not record.lines(month):
                return []
            figure = record.figure(month, now, opened_at=self._admission_opened())
        except (OSError, ValueError):
            return [_item(key=f"availability:{month}:unreadable", capability=AVAILABILITY,
                          component="ServiceOperations", observed_at=now, status="unknown",
                          evidence=f"availability:{month}",
                          limitations=["availability-record-unreadable"])]
        return [_item(
            key=f"availability:{month}:{figure.up}:{figure.down}", capability=AVAILABILITY,
            component="ServiceOperations", observed_at=now,
            status="available" if figure.ratio >= 0.99 else "degraded",
            evidence=f"availability:{month}",
            limitations=[f"availability-permille:{int(figure.ratio * 1000)}",
                         f"budget-left-seconds:{figure.budget_left_seconds}"],
        )]

    def _availability_record(self):
        """The heartbeat's record, in the policy's slots (Step 60(a))."""
        from docsuri_ops.standing.availability import AvailabilityRecord

        return AvailabilityRecord(self.availability_folder,
                                  slot_seconds=int(self.policy.availability_slot_seconds))

    def _admission_opened(self) -> dt.datetime | None:
        """The newest CutoverRecord's `admissionOpenedAt` (Step 60(a), L1-45). The record
        has no `environment`, so it is read without `_records`' filter; before an opening
        the month counts from its start."""
        records = self.ledger.records("cutover-record")
        if not records or not records[-1].get("admissionOpenedAt"):
            return None
        return _parse(records[-1]["admissionOpenedAt"])

    # --- the standing job (Step 60(b), NFR9.7, L1-41) --------------------------------------

    def _standing_job(self, now: dt.datetime) -> list[dict]:
        if self.availability_folder is None:
            return []
        counts = self._standing_failures(now)
        limitations = [f"failed-backups:{counts[0]}", f"failed-verifications:{counts[1]}",
                       f"failed-disposals:{counts[2]}"]
        try:
            last = self._last_run(now)
        except (OSError, ValueError, TypeError):
            return [self._standing_item(now, "unknown", ["availability-record-unreadable",
                                                         *limitations], key="unreadable")]
        if last is None:
            return [self._standing_item(now, "unknown", ["standing-job-unrecorded",
                                                         *limitations], key="unrecorded")]
        age = int((now - last).total_seconds())
        late = age > 2 * int(self.policy.availability_slot_seconds)
        status = "degraded" if late or any(counts) else "available"
        return [self._standing_item(
            last, status, ["standing-job-late", *limitations] if late else limitations,
            key=utc_text(last), age=age)]

    def _standing_item(self, observed: dt.datetime, status: str, limitations: list[str], *,
                       key: str, age: int | None = None) -> dict:
        return _item(key=f"standing-job:{self.environment}:{key}:{','.join(limitations)}",
                     capability=STANDING_JOB, component="ServiceOperations",
                     observed_at=observed, status=status,
                     evidence=f"standing-job:{self.environment}", limitations=limitations,
                     age=age)

    def _last_run(self, now: dt.datetime) -> dt.datetime | None:
        """The newest line's slot across this and the previous Seoul month; a down line
        counts, since the heartbeat writes a line for every slot it runs."""
        from docsuri_ops.standing.availability import month_bounds, month_of

        record = self._availability_record()
        month = month_of(now)
        previous = month_of(month_bounds(month)[0] - dt.timedelta(seconds=1))
        slots = [_parse(line["slot"]) for name in (previous, month)
                 for line in record.lines(name)]
        return max(slots) if slots else None

    def _standing_failures(self, now: dt.datetime) -> tuple[int, int, int]:
        """The standing job's own failed runs over the policy's window, in this
        environment: its scheduled requests that ended failed, refused or expired, each once
        at its `updatedAt` (its own failed set or record counted with it), and each
        disposal at its latest failed attempt."""
        start = now - dt.timedelta(seconds=int(self.policy.error_rate_window_seconds))

        def inside(value) -> bool:
            if not value:
                return False
            moment = _parse(value)
            return start < moment <= now

        failed = {"backup.create": 0, "restore.verify": 0}
        for record in self._records("recovery-request"):
            if (record.get("origin") == SCHEDULED_ORIGIN
                    and record.get("operation") in failed
                    and record.get("state") in FAILED_ENDINGS
                    and inside(record.get("updatedAt"))):
                failed[record["operation"]] += 1
        disposals = sum(1 for record in self._disposable()
                        if not any(record.get(name) for name in CLOSED_FIELDS)
                        and inside(record.get("lastDisposalFailedAt")))
        return failed["backup.create"], failed["restore.verify"], disposals

    def _disposable(self) -> list[dict]:
        """Sets of this environment but a waiting rehearsal set, ledger copies in their
        set's environment, and retained copies; a copy with no environment counts in the
        one this dashboard serves (Step 58(b)'s environments)."""
        from docsuri_ops.cutover.disposal import waiting_rehearsal_sets

        sets = self.ledger.records("backup-set")
        set_environment = {record["backupId"]: record.get("environment") for record in sets}
        waiting = {record["backupId"] for record in waiting_rehearsal_sets(self.ledger)}
        chosen = [record for record in sets if record.get("environment") == self.environment
                  and record["backupId"] not in waiting]
        chosen += [copy for copy in self.ledger.records("ledger-copy")
                   if set_environment.get(copy.get("backupId"), self.environment)
                   == self.environment]
        chosen += list(self.ledger.records("retained-copy"))
        return chosen

    # --- the isolation result (Step 60(d)) ----------------------------------------------

    def _isolation(self) -> list[dict]:
        if self.isolation_folder is None:
            return []
        try:
            candidates = sorted(
                path for path in self.isolation_folder.iterdir()
                if path.suffix == ".json" and path.is_file() and not path.is_symlink())
        except FileNotFoundError:
            return []
        except OSError:
            return [self._isolation_unreadable("folder")]
        if not candidates:
            return []
        newest = candidates[-1]
        try:
            value = json.loads(newest.read_bytes()[:ISOLATION_READ_BYTES])
            checked = _parse(value["checkedAt"])
            result_id = str(value["resultId"])
            stops = [f"stop:{stop['label']}:{stop['expiresAt']}"
                     for stop in value["stopRecords"]]
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            return [self._isolation_unreadable(newest.name)]
        return [_item(key=f"isolation:{result_id}", capability=ISOLATION_RESULT,
                      component="ServiceOperations", observed_at=checked,
                      status="available" if value.get("passed") is True else "unavailable",
                      evidence=f"isolation:{result_id}", limitations=stops)]

    def _isolation_unreadable(self, name: str) -> dict:
        return _item(key=f"isolation:unreadable:{name}", capability=ISOLATION_RESULT,
                     component="ServiceOperations", observed_at=self.clock(), status="unknown",
                     evidence="isolation:unreadable",
                     limitations=["isolation-result-unreadable"])

    # --- failed jobs per lane (Step 60(e), L1-41) ----------------------------------------

    def _lanes(self, now: dt.datetime) -> list[dict]:
        if self.lane_counts is None:
            return []
        from .producers import LANES

        try:
            answers = self.lane_counts.read(now)
        except Exception:  # noqa: BLE001 - one failing source never fails the whole read
            answers = {}
        items = []
        for lane in LANES:
            counts = answers.get(lane)
            if counts is None:
                status, limitations = "unknown", ["lane-count-unavailable"]
            else:
                failed, terminal = int(counts[0]), int(counts[1])
                status = "degraded" if failed > 0 else "available"
                limitations = [f"failed:{failed}", f"terminal:{terminal}"]
            items.append(_item(key=f"lane:{lane}:{','.join(limitations)}", capability=LANE,
                               component=lane, observed_at=now, status=status,
                               evidence=f"lane:{lane}", limitations=limitations))
        return items

    # --- the answers -------------------------------------------------------------------

    def read(self, query: dict) -> dict:
        return page_of(self.items(), query.get("page") or {}, query.get("capability"))

    def incidents(self, query: dict) -> dict:
        records = self._records("service-incident")
        capability = query.get("capability")
        if capability is not None:
            records = [record for record in records if capability in record["capabilities"]]
        unresolved = [r for r in records if r["state"] != "resolved"]
        resolved = [r for r in records if r["state"] == "resolved"]
        ordered = sorted(unresolved, key=lambda r: r["openedAt"], reverse=True) + sorted(
            resolved, key=lambda r: r.get("resolvedAt", r["openedAt"]), reverse=True)
        items = [self._incident(record, self._role(record["incidentId"])) for record in ordered]
        return page_of(items, query.get("page") or {}, maximum=INCIDENT_LIMIT)

    def _role(self, incident_id: str) -> str:
        from .incidents import Incidents

        return Incidents(self.ledger, environment=self.environment).role(incident_id)

    @staticmethod
    def _incident(record: dict, role: str = "ordinary") -> dict:
        evidence = [f"opened:{record['openedAt']}", f"role:{role}"]
        if record.get("diagnosisKey"):
            evidence.append(f"diagnosis:{record['diagnosisKey']}")
        evidence += [f"recovery:{item}" for item in record.get("recoveryRequestIds", [])]
        evidence += list(record.get("evidenceRefs", []))
        value = {
            "incidentId": record["incidentId"], "revision": str(record["revision"]),
            "capabilities": list(record["capabilities"]),
            "correlationIds": list(record["correlationIds"]),
            "state": record["state"], "evidenceRefs": [_id(item) for item in evidence],
        }
        if record["state"] == "resolved":
            value["resolutionKind"] = record["resolutionKind"]
        return value
