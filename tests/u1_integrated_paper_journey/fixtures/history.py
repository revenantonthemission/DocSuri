"""Finite read-only snapshot inventory before diagnostic reconciliation."""

import json

from psycopg import sql

ROW_LIMIT = 2048
PAGE_SIZE = 256
BYTE_LIMIT = 2 * 1024 * 1024


class HistoryBudget:
    def __init__(self):
        self.selected_bytes = 0

    def reserve(self, count, size):
        if count > ROW_LIMIT or size < 0 or self.selected_bytes + size > BYTE_LIMIT:
            raise AssertionError("diagnostic history allocation exceeded; retain evidence and stop")
        self.selected_bytes += size


def inventory(conn, query, params, key, budget):
    """query is a fixed test-owned SELECT, never a caller-supplied expression.

    Call within a repeatable-read transaction. The server computes encoded
    selected-row bytes before any payload decode; pages and the complete result
    remain bounded. All owners' inventories complete before reconciliation.
    """
    source = sql.SQL("SELECT * FROM ({}) selected ORDER BY {} LIMIT {}").format(
        sql.SQL(query), sql.Identifier(key), sql.Literal(ROW_LIMIT + 1)
    )
    measured = conn.execute(
        sql.SQL(
            "SELECT count(*),coalesce(sum(octet_length(row_to_json(known)::text)),0) FROM ({}) known"
        ).format(source),
        params,
    ).fetchone()
    count, allocated = measured
    budget.reserve(count, allocated)
    rows, cursor, decoded_bytes = [], None, 0
    for _ in range(ROW_LIMIT // PAGE_SIZE + 1):
        page = conn.execute(
            sql.SQL(
                "SELECT row_to_json(known)::text FROM ({}) known WHERE (%s::uuid IS NULL OR {}>%s) ORDER BY {} LIMIT %s"
            ).format(source, sql.Identifier(key), sql.Identifier(key)),
            (*params, cursor, cursor, PAGE_SIZE),
        ).fetchall()
        if not page:
            break
        for (raw,) in page:
            decoded_bytes += len(raw.encode("utf-8"))
            if decoded_bytes > allocated or len(rows) >= ROW_LIMIT:
                raise AssertionError("diagnostic inventory changed or exceeded allocation")
            row = json.loads(raw)
            rows.append(row)
        cursor = rows[-1][key]
    if len(rows) != count or decoded_bytes != allocated:
        raise AssertionError("diagnostic inventory changed; refuse reconciliation")
    return rows
