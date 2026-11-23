"""v1's traffic from a Cloudflare request-analytics export (U8 plan Step 31; the person's
decision of 2026-10-24, "Cloudflare's numbers"; BR9.11, Workflow 11).

v1 keeps no per-request access records on this Mac, so v1's route use and request rate
come from an export you take from Cloudflare's dashboard for `docsuri.rvnnt.dev`,
covering whatever the free plan shows. Counts only: the reader reads a row's time, its
request count and, where the export has them, its path and user agent. It never reads
another field, so an address, a country, a ray identifier or anything else in the file
is dropped unread. A path is reduced to its route family (`inventory.route_family`),
which drops the query and every identifier inside it; a user agent is kept only to form
the consumer's opaque reference and the decision subject you are shown.

The accepted shapes (anything else is refused, as is a file over `MAX_BYTES`):

- **JSON**: Cloudflare's GraphQL Analytics API answer for one zone and one group list,
  `{"data": {"viewer": {"zones": [{"<group>": [...]}]}}}` with `errors` absent, null
  or empty. `<group>` is `httpRequests1mGroups`, `httpRequests1hGroups`,
  `httpRequests1dGroups` or `httpRequestsAdaptiveGroups`. Each item has `dimensions`
  with one time key (`datetimeMinute`, `datetimeFiveMinutes`, `datetimeFifteenMinutes`,
  `datetimeHour`, `datetime` or `date`) and optionally `clientRequestPath` and
  `userAgent`, and its count as `sum.requests` or `count`.
- **CSV**: a header row naming one time column (`datetime`, `timestamp`, `time`,
  `date`, `datetimeHour` …, any case) and one count column (`requests`, `count` or
  `total requests`), and optionally a path column (`path`, `clientRequestPath`,
  `request path`) and a user-agent column (`userAgent`, `user agent`, `user-agent`).

The interval is the group's or the time key's (one minute, five, fifteen, an hour, a
day); with a plain time column it is the smallest gap between two distinct times. v1's
peak rate is the busiest interval's requests divided by the interval.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
from collections import Counter
from dataclasses import dataclass

MAX_BYTES = 4 * 1024 * 1024
MAX_ROWS = 100_000
GROUP_INTERVALS = {
    "httpRequests1mGroups": 60, "httpRequests1hGroups": 3600, "httpRequests1dGroups": 86400,
    "httpRequestsAdaptiveGroups": None,
}
TIME_INTERVALS = {
    "datetimeminute": 60, "datetimefiveminutes": 300, "datetimefifteenminutes": 900,
    "datetimehour": 3600, "date": 86400,
}
TIME_KEYS = ("datetimeminute", "datetimefiveminutes", "datetimefifteenminutes",
             "datetimehour", "datetime", "timestamp", "time", "date")
COUNT_KEYS = ("requests", "count", "total requests")
PATH_KEYS = ("clientrequestpath", "path", "request path", "requestpath")
AGENT_KEYS = ("useragent", "user agent", "user-agent")
MIN_INTERVAL = 60


class ExportRefused(ValueError):
    """The export was refused; the message is a fixed reason key."""


@dataclass(frozen=True)
class Row:
    at: dt.datetime
    requests: int
    path: str | None = None
    agent: str | None = None


@dataclass(frozen=True)
class Export:
    rows: tuple[Row, ...]
    interval_seconds: int

    def series(self) -> list[tuple[dt.datetime, int]]:
        totals: Counter = Counter()
        for row in self.rows:
            totals[row.at] += row.requests
        return sorted(totals.items())

    @property
    def total(self) -> int:
        return sum(row.requests for row in self.rows)

    def peak(self) -> tuple[dt.datetime, int]:
        """The busiest interval: its start and its requests (the earliest on a tie)."""
        series = self.series()
        top = max(count for _, count in series)
        return next((at, count) for at, count in series if count == top)

    @property
    def peak_rate(self) -> float:
        return self.peak()[1] / self.interval_seconds

    def window(self) -> tuple[dt.datetime, dt.datetime]:
        series = self.series()
        return series[0][0], series[-1][0] + dt.timedelta(seconds=self.interval_seconds)


def _time(value: object) -> dt.datetime:
    if not isinstance(value, str) or not value or len(value) > 40:
        raise ExportRefused("export-time-unreadable")
    text = value.strip().replace("Z", "+00:00")
    try:
        if len(text) == 10:
            moment = dt.datetime.fromisoformat(text).replace(tzinfo=dt.UTC)
        else:
            moment = dt.datetime.fromisoformat(text.replace(" ", "T", 1))
    except ValueError:
        raise ExportRefused("export-time-unreadable") from None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.UTC)
    return moment.astimezone(dt.UTC)


def _count(value: object) -> int:
    if isinstance(value, bool):
        raise ExportRefused("export-count-unreadable")
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and value.strip().replace(",", "").isdigit():
        number = int(value.strip().replace(",", ""))
    else:
        raise ExportRefused("export-count-unreadable")
    if number < 0:
        raise ExportRefused("export-count-unreadable")
    return number


def _text(value: object) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or len(value) > 2048:
        raise ExportRefused("export-field-unreadable")
    return value


def _pick(names: dict[str, str], keys: tuple[str, ...]) -> str | None:
    """The original name of the first known key the export carries (case-insensitive)."""
    return next((names[key] for key in keys if key in names), None)


def _from_json(value: object) -> tuple[list[Row], int | None]:
    try:
        if value.get("errors"):
            raise ExportRefused("export-carries-errors")
        zones = value["data"]["viewer"]["zones"]
    except (AttributeError, KeyError, TypeError):
        raise ExportRefused("export-shape-unknown") from None
    if not isinstance(zones, list) or len(zones) != 1 or not isinstance(zones[0], dict):
        raise ExportRefused("export-shape-unknown")
    groups = [name for name in zones[0] if name in GROUP_INTERVALS]
    if len(groups) != 1 or not isinstance(zones[0][groups[0]], list):
        raise ExportRefused("export-shape-unknown")
    items = zones[0][groups[0]]
    if len(items) > MAX_ROWS:
        raise ExportRefused("export-too-large")
    rows, interval = [], GROUP_INTERVALS[groups[0]]
    for item in items:
        dimensions = item.get("dimensions") if isinstance(item, dict) else None
        if not isinstance(dimensions, dict):
            raise ExportRefused("export-shape-unknown")
        names = {name.lower(): name for name in dimensions}
        time_key = _pick(names, TIME_KEYS)
        if time_key is None:
            raise ExportRefused("export-shape-unknown")
        interval = interval or TIME_INTERVALS.get(time_key.lower())
        if isinstance(item.get("sum"), dict) and "requests" in item["sum"]:
            requests = _count(item["sum"]["requests"])
        elif "count" in item:
            requests = _count(item["count"])
        else:
            raise ExportRefused("export-shape-unknown")
        path_key, agent_key = _pick(names, PATH_KEYS), _pick(names, AGENT_KEYS)
        rows.append(Row(_time(dimensions[time_key]), requests,
                        _text(dimensions[path_key]) if path_key else None,
                        _text(dimensions[agent_key]) if agent_key else None))
    return rows, interval


def _from_csv(text: str) -> tuple[list[Row], int | None]:
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise ExportRefused("export-shape-unknown") from None
    names = {name.strip().lower(): index for index, name in enumerate(header)}
    lowered = {name: name for name in names}
    time_name, count_name = _pick(lowered, TIME_KEYS), _pick(lowered, COUNT_KEYS)
    if time_name is None or count_name is None:
        raise ExportRefused("export-shape-unknown")
    path_name, agent_name = _pick(lowered, PATH_KEYS), _pick(lowered, AGENT_KEYS)
    rows = []
    for number, cells in enumerate(reader):
        if number >= MAX_ROWS:
            raise ExportRefused("export-too-large")
        if not any(cell.strip() for cell in cells):
            continue
        if len(cells) != len(header):
            raise ExportRefused("export-shape-unknown")
        rows.append(Row(_time(cells[names[time_name]]), _count(cells[names[count_name]]),
                        _text(cells[names[path_name]]) if path_name else None,
                        _text(cells[names[agent_name]]) if agent_name else None))
    return rows, TIME_INTERVALS.get(time_name)


def _gap(rows: list[Row]) -> int:
    times = sorted({row.at for row in rows})
    gaps = [int((later - earlier).total_seconds())
            for earlier, later in zip(times, times[1:], strict=False)]
    positive = [gap for gap in gaps if gap > 0]
    if not positive:
        raise ExportRefused("export-interval-unknown")
    return max(min(positive), MIN_INTERVAL)


def read(raw: bytes) -> Export:
    """The export's counts, or `ExportRefused` with a fixed reason."""
    if len(raw) > MAX_BYTES:
        raise ExportRefused("export-too-large")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ExportRefused("export-shape-unknown") from None
    stripped = text.lstrip()
    if stripped.startswith("{"):
        try:
            value = json.loads(stripped)
        except ValueError:
            raise ExportRefused("export-shape-unknown") from None
        rows, interval = _from_json(value)
    else:
        rows, interval = _from_csv(text)
    if not rows:
        raise ExportRefused("export-empty")
    return Export(tuple(rows), interval or _gap(rows))
