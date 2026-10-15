"""U3 Discovery citations: bounded, labelled, provider-neutral traversal.

Distinct-node/depth/request bounds are enforced server-side; cycles and
duplicate nodes cannot create unbounded traversal. Unknown, stale or partial
provider data is labelled and edges are never fabricated. Saving a referenced
paper calls the Library operation; Discovery never writes Library records
(BR5.1-5.2).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from backend.transactions import Authority, guard
from backend.u3_policy import (
    CITATION_COVERAGE,
    CITATION_FRESHNESS,
    CITATION_POLICY,
    MAX_CITATION_DEPTH,
    MAX_CITATION_NODES,
    MAX_CITATION_REQUESTS,
    require_policy,
)
from psycopg.types.json import Jsonb


class ProviderUnavailable(RuntimeError):
    """The citation provider cannot answer; the view is labelled, never invented."""


class BudgetExhausted(RuntimeError):
    """The finite provider request allocation for this window is spent."""


class CitationExplorer:
    def __init__(self, transactions, provider, *, clock=None):
        self.transactions = transactions
        self.provider = provider
        self.clock = clock or (lambda: datetime.now(UTC))

    def explore(self, authority: Authority, request: dict) -> dict:
        require_policy(
            request.get("traversalPolicy"), CITATION_POLICY, name="traversal policy"
        )
        paper = request.get("paper") or {}
        root_version = paper.get("versionId")
        if not isinstance(root_version, str) or not 1 <= len(root_version) <= 160:
            raise ValueError("citation root outside finite policy")
        direction = request.get("direction")
        if direction not in ("cited", "citing", "both"):
            raise ValueError("unknown citation direction")
        self._spend_budget(authority)

        def read(conn):
            guard(conn, authority)
            root = conn.execute(
                "SELECT * FROM corpus.current_eligibility(%s)", (root_version,)
            ).fetchone()
            if root["disposition"] != "available":
                return self._labelled(
                    str(uuid4()),
                    paper,
                    direction,
                    nodes=[
                        {
                            "nodeId": root_version,
                            "paper": None,
                            "title": None,
                            "sourceUrl": None,
                            "disposition": _node_disposition(root["disposition"], False),
                        }
                    ],
                    edges=[],
                    freshness="unknown",
                    coverage="unavailable",
                    limitations=["인용 정보를 제공할 수 없는 자료입니다."],
                    provider_revision="unavailable",
                )
            try:
                value = self.provider.read(
                    root_version,
                    direction,
                    max_nodes=MAX_CITATION_NODES,
                    max_depth=MAX_CITATION_DEPTH,
                    max_requests=MAX_CITATION_REQUESTS,
                )
            except ProviderUnavailable:
                return self._labelled(
                    str(uuid4()),
                    paper,
                    direction,
                    nodes=[
                        {
                            "nodeId": root_version,
                            "paper": paper,
                            "title": None,
                            "sourceUrl": None,
                            "disposition": "eligible",
                        }
                    ],
                    edges=[],
                    freshness="unknown",
                    coverage="unavailable",
                    limitations=[
                        "인용 제공자를 사용할 수 없습니다. 이미 저장한 참조는 그대로 유지됩니다."
                    ],
                    provider_revision="unavailable",
                )
            normalized = _normalize_provider_value(value, root_version, direction)
            nodes = []
            for node in normalized["nodes"]:
                version = node.get("versionId")
                eligibility_revision = None
                disposition = "unknown"
                if version:
                    row = conn.execute(
                        "SELECT * FROM corpus.current_eligibility(%s)", (version,)
                    ).fetchone()
                    eligibility_revision = row["eligibility_revision"]
                    disposition = _node_disposition(
                        row["disposition"], row["disposition"] == "available"
                    )
                nodes.append(
                    {
                        "nodeId": version or node["nodeId"],
                        "paper": (
                            {
                                "paperId": node["paperId"],
                                "versionId": version,
                                "eligibilityRevision": str(eligibility_revision)
                                if eligibility_revision
                                else "unknown",
                            }
                            if version and node.get("paperId")
                            else None
                        ),
                        "title": node.get("title"),
                        "sourceUrl": node.get("sourceUrl"),
                        "disposition": disposition,
                    }
                )
            snapshot_id = str(uuid4())
            conn.execute(
                "INSERT INTO discovery.citation_snapshot(id,root_version_id,direction,depth,"
                "nodes,edges,provenance,freshness,coverage,provider_revision,account_id) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    snapshot_id,
                    root_version,
                    direction,
                    normalized["depth"],
                    Jsonb(nodes),
                    Jsonb(normalized["edges"]),
                    Jsonb(normalized["provenance"]),
                    normalized["freshness"],
                    normalized["coverage"],
                    normalized["providerRevision"],
                    authority.account_id,
                ),
            )
            return self._labelled(
                snapshot_id,
                paper,
                direction,
                nodes=nodes,
                edges=normalized["edges"],
                freshness=normalized["freshness"],
                coverage=normalized["coverage"],
                limitations=normalized["limitations"],
                provider_revision=normalized["providerRevision"],
            )

        return self.transactions.run("discovery", read)

    def _spend_budget(self, authority: Authority) -> None:
        """One bounded provider request allocation per account and five-minute window."""

        def write(conn):
            guard(conn, authority)
            window = conn.execute(
                "SELECT date_trunc('hour', clock_timestamp()) "
                "+ (floor(extract(minute from clock_timestamp()) / 5) * interval '5 minutes') "
                "AS window"
            ).fetchone()["window"]
            conn.execute(
                "INSERT INTO discovery.provider_budget(account_id,window_start) VALUES(%s,%s) "
                "ON CONFLICT (account_id,window_start) DO NOTHING",
                (authority.account_id, window),
            )
            row = conn.execute(
                "SELECT * FROM discovery.provider_budget WHERE account_id=%s AND "
                "window_start=%s FOR UPDATE",
                (authority.account_id, window),
            ).fetchone()
            if row["requests"] >= MAX_CITATION_REQUESTS:
                raise BudgetExhausted("citation provider request allocation exhausted")
            conn.execute(
                "UPDATE discovery.provider_budget SET requests=requests+1 WHERE account_id=%s "
                "AND window_start=%s",
                (authority.account_id, window),
            )

        self.transactions.run("discovery", write)

    @staticmethod
    def _labelled(snapshot_id, paper, direction, *, nodes, edges, freshness, coverage,
                  limitations, provider_revision) -> dict:
        if freshness not in CITATION_FRESHNESS or coverage not in CITATION_COVERAGE:
            raise ValueError("citation labels outside the vocabulary")
        return {
            "snapshotId": snapshot_id,
            "root": paper,
            "direction": direction,
            "nodes": nodes,
            "edges": edges,
            "freshness": freshness,
            "coverage": coverage,
            "limitations": limitations[:8],
            "providerRevision": provider_revision,
        }


def _node_disposition(disposition: str, eligible: bool) -> str:
    return {
        "available": "eligible",
        "withdrawn": "withdrawn",
        "restricted": "restricted",
        "absent": "incomplete",
    }.get(disposition, "unknown" if not eligible else "eligible")


def _normalize_provider_value(value: dict, root_version: str, direction: str) -> dict:
    """Validate one provider payload into bounded, labelled traversal output."""
    if not isinstance(value, dict):
        raise ProviderUnavailable("malformed provider payload")
    nodes = value.get("nodes")
    edges = value.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ProviderUnavailable("malformed provider payload")
    distinct: dict[str, dict] = {}
    truncated = bool(value.get("truncated"))
    for node in nodes:
        if not isinstance(node, dict):
            raise ProviderUnavailable("malformed provider node")
        identity = node.get("versionId") or node.get("nodeId")
        if not isinstance(identity, str) or not 1 <= len(identity) <= 160:
            continue  # a node without stable identity cannot be traversed
        depth = node.get("depth", 1)
        if type(depth) is not int or not 0 <= depth <= MAX_CITATION_DEPTH:
            truncated = True
            continue
        if identity in distinct:
            continue
        distinct[identity] = {
            "nodeId": identity,
            "versionId": node.get("versionId"),
            "paperId": node.get("paperId"),
            "title": node.get("title"),
            "sourceUrl": node.get("sourceUrl"),
            "depth": depth,
        }
    if len(distinct) > MAX_CITATION_NODES:
        ordered = sorted(distinct.values(), key=lambda item: (item["depth"], item["nodeId"]))
        distinct = {item["nodeId"]: item for item in ordered[:MAX_CITATION_NODES]}
        truncated = True
    allowed = set(distinct) | {root_version}
    kept_edges = []
    seen_edges = set()
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        source, target = edge.get("fromNodeId"), edge.get("toNodeId")
        source_url = edge.get("sourceUrl")
        if source not in allowed or target not in allowed:
            continue
        if not isinstance(source_url, str) or not source_url.startswith(("https://", "http://")):
            continue
        key = (source, target, source_url)
        if key in seen_edges:
            continue
        seen_edges.add(key)
        kept_edges.append(
            {
                "fromNodeId": source,
                "toNodeId": target,
                "sourceUrl": source_url,
                "observedAt": edge.get("observedAt")
                or datetime.now(UTC).isoformat(),
            }
        )
    if len(kept_edges) > 2 * MAX_CITATION_NODES:
        kept_edges = kept_edges[: 2 * MAX_CITATION_NODES]
        truncated = True
    freshness = value.get("freshness", "unknown")
    coverage = value.get("coverage", "partial")
    if freshness not in CITATION_FRESHNESS:
        freshness = "unknown"
    if coverage not in CITATION_COVERAGE:
        coverage = "partial"
    if truncated and coverage == "complete":
        coverage = "partial"
    provider_revision = str(value.get("providerRevision", "unknown"))[:64]
    limitations = [
        str(item)[:200] for item in value.get("limitations", []) if isinstance(item, str)
    ][:4]
    if truncated:
        limitations.append("탐색 한도에 도달했습니다. 표시된 범위까지만 제공됩니다.")
    if freshness != "fresh":
        limitations.append("인용 정보의 최신성이 보장되지 않습니다.")
    if coverage == "partial":
        limitations.append("일부 인용 정보만 제공됩니다.")
    return {
        "nodes": list(distinct.values()),
        "edges": kept_edges,
        "freshness": freshness,
        "coverage": coverage,
        "providerRevision": provider_revision,
        "limitations": limitations,
        "depth": min(
            (node["depth"] for node in distinct.values()), default=0
        ),
        "provenance": {
            "providerRevision": provider_revision,
            "fetchedAt": datetime.now(UTC).isoformat(),
            "truncated": truncated,
        },
    }


class FixtureCitationProvider:
    """Local deterministic provider fixture; success is labelled synthetic."""

    def __init__(self, records: dict, *, freshness: str = "fresh", fail: bool = False):
        self.records = records
        self.freshness = freshness
        self.fail = fail

    def read(self, root_version, direction, *, max_nodes, max_depth, max_requests) -> dict:
        if self.fail:
            raise ProviderUnavailable("fixture provider failure")
        record = self.records.get(root_version)
        if record is None:
            return {
                "providerRevision": "u3-fixture-citations-1",
                "freshness": "unknown",
                "coverage": "unavailable",
                "nodes": [],
                "edges": [],
                "limitations": ["로컬 합성 인용 데이터가 없습니다."],
            }
        nodes, edges = [], []
        frontier = [(root_version, 0)]
        visited = {root_version}
        requests = 0
        truncated = False
        while frontier:
            current, depth = frontier.pop(0)
            if depth >= max_depth:
                if record.get(current, {}).get(direction) or (
                    direction == "both" and record.get(current)
                ):
                    truncated = True
                continue
            for link in _links(record.get(current, {}), direction):
                requests += 1
                if requests > max_requests:
                    truncated = True
                    break
                target = link["versionId"]
                edges.append(
                    {
                        "fromNodeId": current,
                        "toNodeId": target,
                        "sourceUrl": link["sourceUrl"],
                        "observedAt": link.get("observedAt"),
                    }
                )
                if target not in visited and len(visited) <= max_nodes:
                    visited.add(target)
                    nodes.append(dict(link, depth=depth + 1))
                    if len(visited) > max_nodes:
                        truncated = True
                        continue
                    frontier.append((target, depth + 1))
            if requests > max_requests:
                break
        return {
            "providerRevision": "u3-fixture-citations-1",
            "freshness": self.freshness,
            "coverage": "partial" if truncated else "complete",
            "nodes": nodes,
            "edges": edges,
            "truncated": truncated,
        }


def _links(record: dict, direction: str) -> list[dict]:
    if direction == "both":
        return [*record.get("cited", []), *record.get("citing", [])]
    return list(record.get(direction, []))
