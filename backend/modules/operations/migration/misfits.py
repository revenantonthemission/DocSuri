"""Misfits and your decisions on them (U8 plan Step 31; BR8.1, BR8.9, Workflow 10).

A record that cannot be imported as it is becomes a misfit: its kind, its v1 source id
and its reason. Each (kind, reason) gets your decision, recorded as a MisfitDecision:

- `map`, with one of the mapping rules below, which the owners' imports apply;
- `archive-only`: not imported, kept only in the retained v1 copies;
- `drop`: not imported, recorded.

`Decisions` is the set current at one moment, read from the ledger, with its digest; a
run records the digest of the decisions current at its start. The kinds Q13 did not
name are counted with reason `not-in-scope` and default to archive-only until you decide
otherwise (BR8.1). `PROPOSALS` holds Workflow 10's proposed decisions, shown to you; none
applies until you record it.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

import rfc8785

DECISIONS = ("map", "archive-only", "drop")
NOT_IN_SCOPE = "not-in-scope"
NOT_IN_SCOPE_KINDS = (
    "followed-topic", "digest-settings", "glossary", "saved-search", "search-history",
    "behavior-event", "plan-record", "private-upload", "research-history", "novelty-history",
    "summary",
)
# The mapping rules the owners' imports apply, one per (kind, reason) a `map` may take.
MAPPING_RULES = {
    ("account", "required-field-without-source"): "display-name-from-orcid-or-email",
    ("account", "locked-in-v1"): "import-reset-required",
    ("paper-embedding", "embedding-provenance-unproven"): "re-embed-pinned-model",
    ("saved-paper", "duplicate-by-version"): "collapse-into-one",
}
# Workflow 10's table: every proposal is yours to accept or change.
PROPOSALS = {
    ("account", "required-field-without-source"): "map",
    ("account", "unverified-in-v1"): "archive-only",
    ("account", "locked-in-v1"): "map",
    ("account", "closed-in-v1"): "archive-only",
    ("account", "no-email"): "archive-only",
    ("account", "email-case-conflict"): "archive-only",
    ("identity-link", "unconfirmed-link"): "drop",
    ("identity-link", "duplicate-provider-link"): "archive-only",
    ("preferences", "no-v2-home"): "archive-only",
    ("paper", "exceeds-v2-limit"): "archive-only",
    ("paper", "ineligible-in-v2"): "archive-only",
    ("paper-content", "content-shape-unconvertible"): "archive-only",
    ("paper-embedding", "embedding-provenance-unproven"): "map",
    ("paper-figure", "no-v2-home"): "archive-only",
    ("saved-paper", "duplicate-by-version"): "map",
    **{(kind, NOT_IN_SCOPE): "archive-only" for kind in NOT_IN_SCOPE_KINDS},
}


@dataclass(frozen=True)
class Decision:
    decision: str
    mapping_rule: str | None = None
    approval_id: str | None = None
    frozen: bool = False


@dataclass(frozen=True)
class Decisions:
    """The decisions current at one moment, by (kind, reason)."""

    items: Mapping[tuple[str, str], Decision] = field(default_factory=dict)
    # A final run: anything it meets for the first time takes archive-only (BR8.9).
    fallback: str | None = None

    def for_final_run(self) -> Decisions:
        return Decisions(self.items, fallback="archive-only")

    @classmethod
    def from_records(cls, records: Iterable[dict]) -> Decisions:
        items = {}
        for record in records:
            items[(record["kind"], record["reasonKey"])] = Decision(
                record["decision"], record.get("mappingRule"), record.get("approvalId"),
                bool(record.get("frozen")))
        return cls(items)

    @classmethod
    def from_ledger(cls, ledger) -> Decisions:
        return cls.from_records(ledger.records("misfit-decision"))

    def of(self, kind: str, reason: str) -> str | None:
        """Your decision, or for a kind outside Q13 its archive-only default."""
        decided = self.items.get((kind, reason))
        if decided is not None:
            return decided.decision
        return "archive-only" if reason == NOT_IN_SCOPE else self.fallback

    def maps(self, kind: str, reason: str) -> bool:
        """Whether your decision maps this (kind, reason) by its one mapping rule."""
        decided = self.items.get((kind, reason))
        rule = MAPPING_RULES.get((kind, reason))
        return (decided is not None and decided.decision == "map" and rule is not None
                and decided.mapping_rule == rule)

    def rules(self, kind: str) -> frozenset[str]:
        """The mapping rules your decisions approved for one kind."""
        return frozenset(
            rule for (rule_kind, reason), rule in MAPPING_RULES.items()
            if rule_kind == kind and self.maps(kind, reason)
        )

    def undecided(self, pairs: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
        return sorted({pair for pair in pairs if self.of(*pair) is None})

    def digest(self) -> str:
        """The digest of the decisions current now, recorded by every run at its start."""
        value = [
            {"kind": kind, "reasonKey": reason, "decision": item.decision,
             "mappingRule": item.mapping_rule}
            for (kind, reason), item in sorted(self.items.items())
        ]
        return hashlib.sha256(rfc8785.dumps(value)).hexdigest()


def disposition(decisions: Decisions, kind: str, reason: str) -> str:
    """How a misfit counts in the report: `mapped` when your decision maps it,
    `excluded` when it archives or drops it, `skipped` while it is undecided."""
    decided = decisions.of(kind, reason)
    if decided == "map":
        return "mapped" if decisions.maps(kind, reason) else "skipped"
    if decided in ("archive-only", "drop"):
        return "excluded"
    return "skipped"
