"""Bounded owner store observations for truthful local readiness.

Each installed owner provides one bounded read of its own store through its own
pool. The assembly records the results through the operations owner and derives
service readiness from fresh observations: a missing store, schema, relation or
read privilege yields an unavailable observation, and a missing or stale
observation never passes as ready. Observations carry counts and guard-function
presence only - never source text, credentials or account identifiers.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime

import psycopg
from psycopg.types.json import Jsonb

from .transactions import Busy, OwnerTransactions

# The finite validity of one observation. The supervisor renews observations on
# its bounded interval; readiness re-probes within the same bounded call when
# the stored observation is missing or stale.
OBSERVATION_SECONDS = 300


@dataclass(frozen=True)
class OwnerProbe:
    """One bounded owner read; evidence is counts and fixed shape checks only."""

    statement: str

    def run(self, conn) -> dict:
        row = conn.execute(self.statement).fetchone()
        return {key: int(value) for key, value in row.items()}


# Key relation per owner plus the guard function that owner's security depends
# on. The probe proves connect + schema + relation + read privilege; an empty
# store is a normal ready state, not a failure.
PROBES = {
    "accounts": OwnerProbe(
        "SELECT (SELECT count(*) FROM accounts.account) AS accounts,"
        " (SELECT count(*) FROM accounts.session) AS sessions,"
        " (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace"
        "  WHERE n.nspname='accounts' AND p.proname='guard_session') AS guard_functions"
    ),
    "corpus": OwnerProbe(
        "SELECT (SELECT count(*) FROM corpus.version) AS versions,"
        " (SELECT count(*) FROM corpus.publication) AS publications,"
        " (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace"
        "  WHERE n.nspname='corpus' AND p.proname='guard_version') AS guard_functions"
    ),
    "discovery": OwnerProbe(
        "SELECT (SELECT count(*) FROM discovery.execution) AS executions,"
        " (SELECT count(*) FROM corpus.projection) AS projections"
    ),
    "library": OwnerProbe(
        "SELECT (SELECT count(*) FROM library.saved_paper) AS saved_papers,"
        " (SELECT count(*) FROM library.history) AS history"
    ),
    "personalization": OwnerProbe(
        "SELECT (SELECT count(*) FROM personalization.settings) AS settings,"
        " (SELECT count(*) FROM personalization.behavior) AS behavior"
    ),
    "usage": OwnerProbe(
        "SELECT (SELECT count(*) FROM usage.entitlement) AS entitlements,"
        " (SELECT count(*) FROM usage.reservation) AS reservations"
    ),
    "assistance": OwnerProbe(
        "SELECT (SELECT count(*) FROM assistance.job) AS jobs,"
        " (SELECT count(*) FROM assistance.result) AS results,"
        " (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace"
        "  WHERE n.nspname='assistance' AND p.proname='read_glossary') AS guard_functions"
    ),
    "operations": OwnerProbe(
        "SELECT (SELECT count(*) FROM operations.observation) AS observations,"
        " (SELECT count(*) FROM operations.incident) AS incidents"
    ),
}

AUTHORITY_PROBES = ("accounts", "corpus", "assistance")
CORPUS_PROBES = ("discovery", "library", "assistance")


def _reason(exc: BaseException) -> str:
    """Map a probe failure to a finite safe reason key; never surface raw text."""
    if isinstance(exc, Busy):
        return "observation.allocationExhausted"
    if isinstance(exc, (psycopg.errors.InsufficientPrivilege, psycopg.errors.UndefinedTable)):
        return "observation.storeDenied"
    if isinstance(
        exc,
        (psycopg.OperationalError, psycopg.InterfaceError, psycopg.errors.InvalidSchemaName),
    ):
        return "observation.storeUnavailable"
    if isinstance(exc, ValueError):
        # A closed pool, an unknown owner or an expired synthetic retention
        # window all mean this process cannot observe the store right now.
        return "observation.storeUnavailable"
    return "observation.probeFailed"


def probe_owner(transactions: OwnerTransactions, owner: str) -> dict:
    """One bounded observation of one owner store; never raises to the caller."""
    observed_at = time.time()
    try:
        evidence = transactions.run(owner, PROBES[owner].run)
        result = {"disposition": "available", "evidence": evidence}
    except KeyboardInterrupt:
        raise
    except BaseException as exc:  # bounded: every failure becomes an observation
        result = {"disposition": "unavailable", "evidence": {"reasonKey": _reason(exc)}}
    return {
        "capability": owner,
        "disposition": result["disposition"],
        "observedAt": observed_at,
        "expiresAt": observed_at + OBSERVATION_SECONDS,
        "evidence": result["evidence"],
    }


def observe_all(transactions: OwnerTransactions) -> dict[str, dict]:
    return {owner: probe_owner(transactions, owner) for owner in PROBES}


def record(transactions: OwnerTransactions, observations: dict[str, dict]) -> None:
    """Operations-owned write of current observations; ids and counts only."""

    def write(conn):
        for capability in sorted(observations):
            row = observations[capability]
            conn.execute(
                "INSERT INTO operations.observation(capability,disposition,observed_at,"
                "expires_at,evidence) VALUES(%s,%s,to_timestamp(%s),to_timestamp(%s),%s) "
                "ON CONFLICT(capability) DO UPDATE SET disposition=excluded.disposition,"
                "observed_at=excluded.observed_at,expires_at=excluded.expires_at,"
                "evidence=excluded.evidence",
                (
                    capability,
                    row["disposition"],
                    row["observedAt"],
                    row["expiresAt"],
                    Jsonb(row["evidence"]),
                ),
            )

    transactions.run("operations", write)


def fresh(transactions: OwnerTransactions) -> dict[str, dict]:
    """Currently valid observations; an unavailable store raises to the caller."""

    def read(conn):
        rows = conn.execute(
            "SELECT capability,disposition,observed_at,expires_at,evidence "
            "FROM operations.observation WHERE expires_at > clock_timestamp()"
        ).fetchall()
        return {row["capability"]: row for row in rows}

    return transactions.run("operations", read)


def readiness(transactions: OwnerTransactions, required: set[str]) -> dict:
    """Derive readiness from fresh observations, re-probing within this call.

    Missing or stale evidence is refreshed by one bounded probe per owner; the
    probe result is recorded so the next read reuses the fresh observation.
    """
    try:
        rows = fresh(transactions)
    except KeyboardInterrupt:
        raise
    except BaseException:
        # The operations store itself is unreadable: nothing may pass.
        return {
            "ready": False,
            "missing": sorted(required),
            "observations": [
                {
                    "capability": owner,
                    "status": "unknown",
                    "reasonKey": "observation.storeUnavailable",
                }
                for owner in sorted(required)
            ],
        }
    missing = sorted(
        owner
        for owner in required
        if owner not in rows or rows[owner]["disposition"] not in ("available", "degraded")
    )
    if missing:
        refreshed = {owner: probe_owner(transactions, owner) for owner in missing}
        try:
            record(transactions, refreshed)
        except KeyboardInterrupt:
            raise
        except BaseException:
            pass  # a failed write of evidence never turns a failure into ready
        for owner, row in refreshed.items():
            rows[owner] = {
                "capability": owner,
                "disposition": row["disposition"],
                "observed_at": datetime.fromtimestamp(row["observedAt"], UTC),
                "expires_at": datetime.fromtimestamp(row["expiresAt"], UTC),
                "evidence": row["evidence"],
            }
        missing = sorted(
            owner
            for owner in required
            if rows.get(owner, {}).get("disposition") not in ("available", "degraded")
        )
    return {
        "ready": not missing,
        "missing": missing,
        "observations": [
            {
                "capability": owner,
                "status": (
                    rows[owner]["disposition"]
                    if owner in rows and rows[owner]["disposition"] in ("available", "degraded")
                    else "unknown"
                ),
                "observedAt": (
                    rows[owner]["observed_at"].isoformat()
                    if owner in rows and rows[owner]["observed_at"] is not None
                    else None
                ),
                "expiresAt": (
                    rows[owner]["expires_at"].isoformat()
                    if owner in rows and rows[owner]["expires_at"] is not None
                    else None
                ),
                "evidence": rows.get(owner, {}).get("evidence") or {},
            }
            for owner in sorted(required)
        ],
    }
