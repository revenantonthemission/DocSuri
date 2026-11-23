"""The import phases (U8 plan Step 31; BR8.1–BR8.10, BR8.13, BR8.14, Workflow 9 step 3).

One pass reads the run's copy of v1 (`V1Source`) and writes every record through its
owner's import operation, under trusted composition authority, in BR8.4's order:

1. accounts (AccountAccess's `importAccount`); emails differing only in letter case are
   all `email-case-conflict`, and none of them is merged or guessed;
2. identity links (`importIdentityLink`);
3. preferences (Personalization's `importSettings`): the enabled flag, onboarding and
   the summary and translation defaults; interest weights have no v2 home;
4. papers with their content and embeddings (CorpusContent's `importPaper`), matched by
   their canonical identity; v1's vectors are never reused, and figures have no v2 home;
5. saved papers (Library's `importSavedPaper`), version suffixes collapsed into one;
6. the kinds Q13 did not name, counted with reason `not-in-scope`.

A record whose account or paper version was not imported is `dependency-not-migrated`.
Target identities are deterministic (`identities.target_id`), so a second pass over the
same snapshot reports nothing imported and nothing updated (BR8.3). Each kind's `Tally`
holds what the parity report needs: counts, misfits, and the stored digests the owners
answered with, which the report compares with each owner's own parity read.

`main` is `ops/bin/docsuri-migration-import <phase>`'s entry: the service account runs
one word of `WORDS` with a bounded JSON document naming the run's databases.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID

from .identities import (
    arxiv_parts,
    canonical_paper,
    link_source_id,
    target_id,
    version_identity,
)
from .misfits import NOT_IN_SCOPE, Decisions, disposition
from .v1_source import V1Account, V1Source

if TYPE_CHECKING:
    from backend.modules.corpus.paper_import import LimitRecord

# `usage` follows the accounts (the person's decision of 2026-10-23, "Grant migrated
# accounts"): UsageEntitlements' `grantImportedUsage` for each imported account.
PHASES = ("accounts", "usage", "identity-links", "preferences", "papers", "saved-papers",
          "not-in-scope")
# The misfit kind of an owner's refusal, where it differs from the source kind.
REFUSAL_KINDS = {"content-shape-unconvertible": "paper-content"}
LANGUAGE, APPEARANCE = "ko", "system"
MAX_DISPLAY_NAME = 256


@dataclass
class Tally:
    kind: str
    source: int = 0
    imported: int = 0
    unchanged: int = 0
    updated: int = 0
    mapped: int = 0
    skipped: Counter = field(default_factory=Counter)
    excluded: Counter = field(default_factory=Counter)
    digests: list[str] = field(default_factory=list)
    misfits: list[tuple[str, str, str]] = field(default_factory=list)
    # The paper tally's corpus limit record (L1-79): each limit's value, the largest value
    # measured among the papers that landed, and how many papers each limit refused.
    limits: LimitRecord | None = None

    def outcome(self, result: dict, source_id: str, decisions: Decisions) -> bool:
        """Count one owner answer; True when the record is now in v2."""
        self.source += 1
        state = result["disposition"]
        if state in ("imported", "unchanged", "updated"):
            setattr(self, state, getattr(self, state) + 1)
            self.digests.append(result["storedDigest"])
            return True
        reason = result["reasonKey"]
        self._misfit(REFUSAL_KINDS.get(reason, self.kind), source_id, reason, decisions,
                     counted=True)
        return False

    def misfit(self, source_id: str, reason: str, decisions: Decisions, *,
               kind: str | None = None, counted: bool = True) -> None:
        """A misfit the tool finds before any owner is asked."""
        if counted:
            self.source += 1
        self._misfit(kind or self.kind, source_id, reason, decisions, counted=counted)

    def _misfit(self, kind: str, source_id: str, reason: str, decisions: Decisions, *,
                counted: bool) -> None:
        self.misfits.append((kind, source_id, reason))
        if not counted:
            return
        how = disposition(decisions, kind, reason)
        if how == "mapped":
            self.mapped += 1
        elif how == "excluded":
            self.excluded[decisions.of(kind, reason)] += 1
        else:
            self.skipped[reason] += 1

    def as_dict(self) -> dict:
        value = {
            "kind": self.kind, "source": self.source, "imported": self.imported,
            "unchanged": self.unchanged, "updated": self.updated, "mapped": self.mapped,
            "skipped": dict(sorted(self.skipped.items())),
            "excluded": dict(sorted(self.excluded.items())),
        }
        if self.limits is not None:
            value["limits"] = self.limits.as_dict()
        return value


@dataclass
class Owners:
    """The owners' import operations on the run's target database: the four of BR8.4
    and UsageEntitlements' imported usage."""

    accounts: object
    settings: object
    papers: object
    saved: object
    usage: object = None

    @classmethod
    def for_target(cls, transactions, *, files, limits, embedder, vector_policy) -> Owners:
        from backend.modules.accounts.control_policy import for_realm
        from backend.modules.accounts.services.v1_import import V1AccountImport
        from backend.modules.corpus.paper_import import PaperImport
        from backend.modules.library.repository.imports import SavedPaperImports
        from backend.modules.personalization.import_repository import SettingsImports
        from backend.modules.plans.u8_usage import ImportedUsage

        # The policy of the realm the run imports into: production's in production.
        policy = for_realm(transactions.profile.realm)
        if policy is None or transactions.profile.realm == "account-controls":
            raise ValueError("an import runs only into a complete realm")
        return cls(
            V1AccountImport(transactions), SettingsImports(transactions),
            PaperImport(transactions, files, limits=limits, embedder=embedder,
                        vector_policy=vector_policy),
            SavedPaperImports(transactions), ImportedUsage(transactions, policy),
        )


def _display_name(account: V1Account, orcid_names: dict[str, str]) -> str | None:
    """The mapping rule `display-name-from-orcid-or-email`: the ORCID name when linked,
    otherwise the part of the email before @."""
    name = orcid_names.get(account.source_id)
    if not name and account.email and "@" in account.email:
        name = account.email.split("@", 1)[0]
    if not name:
        return None
    return name.encode()[:MAX_DISPLAY_NAME].decode(errors="ignore") or None


def _no_boundary(kind: str) -> None:
    """The default boundary: nothing stops the import (U8 plan Step 68(b))."""


class ImportRun:
    def __init__(self, source: V1Source, owners: Owners, decisions: Decisions, *,
                 clock: Callable[[], dt.datetime],
                 boundary: Callable[[str], None] | None = None,
                 skip_papers: Iterable[str] = ()):
        """`boundary(kind)` is called with `"phase"` before each phase and with `"paper"`
        before each paper is read, and may raise to stop the import there (S3, the disk
        guard's `boundary`). `skip_papers` names the source ids of papers an earlier pass
        of the same run recorded as refused by the database's time limits: each is
        counted as that misfit without asking CorpusContent again (Step 68(h))."""
        self.source, self.owners, self.decisions, self.clock = (
            source, owners, decisions, clock)
        self.boundary = boundary or _no_boundary
        self.skip_papers = frozenset(skip_papers)
        self.tallies: dict[str, Tally] = {}
        self.accounts: dict[str, UUID] = {}
        self.versions: dict[str, list[tuple[int, str]]] = {}

    def tally(self, kind: str) -> Tally:
        return self.tallies.setdefault(kind, Tally(kind))

    def run(self) -> dict[str, Tally]:
        for phase in PHASES:
            self.boundary("phase")
            getattr(self, "_" + phase.replace("-", "_"))()
        return self.tallies

    # --- 1. accounts ----------------------------------------------------------------

    def _accounts(self) -> None:
        tally, decisions = self.tally("account"), self.decisions
        accounts = self.source.accounts()
        lowered = Counter(item.email.lower() for item in accounts if item.email)
        names = {link.account_id: link.orcid_name for link in self.source.links()
                 if link.provider == "orcid" and link.confirmed and link.orcid_name}
        rules = decisions.rules("account")
        for account in accounts:
            if account.email and lowered[account.email.lower()] > 1:
                tally.misfit(account.source_id, "email-case-conflict", decisions)
                continue
            name = (_display_name(account, names)
                    if "display-name-from-orcid-or-email" in rules else None)
            target = target_id("account", account.source_id)
            result = self.owners.accounts.import_account(
                target, source_key=account.source_id, email=account.email,
                email_verified=account.state == "active",
                password_verifier=account.password_hash, state=account.state,
                role=account.role, created_at=account.created_at, display_name=name,
                mapping=rules)
            if tally.outcome(result, account.source_id, decisions):
                self.accounts[account.source_id] = target
                # Moved by a mapping rule: still a misfit of its kind, reported as mapped.
                tally.misfit(account.source_id, "required-field-without-source", decisions,
                             counted=False)
                if account.state == "locked":
                    tally.misfit(account.source_id, "locked-in-v1", decisions, counted=False)

    # --- 1b. imported usage ----------------------------------------------------------
    #
    # Each imported account's grant (`grantImportedUsage`), counted by outcome as its own
    # kind: granted (`imported`), already held (`unchanged`), or skipped by reason (an
    # account not active in v2). An account that was not imported is never asked.

    def _usage(self) -> None:
        if self.owners.usage is None:
            return
        tally = self.tally("usage-grant")
        for source_id, target in self.accounts.items():
            result = self.owners.usage.grant_imported(target)
            if result["disposition"] == "refused":
                tally.source += 1
                tally.skipped[result["reasonKey"]] += 1
                continue
            tally.outcome(result, source_id, self.decisions)

    # --- 2. identity links ------------------------------------------------------------

    def _identity_links(self) -> None:
        tally = self.tally("identity-link")
        for link in self.source.links():
            source_id = link_source_id(link.provider, link.subject)
            if link.provider not in ("google", "orcid"):
                tally.misfit(source_id, "no-v2-home", self.decisions)
                continue
            account = self.accounts.get(link.account_id) or target_id("account",
                                                                       link.account_id)
            result = self.owners.accounts.import_identity_link(
                target_id("identity-link", source_id), source_key=source_id,
                account_id=account, provider=link.provider, subject=link.subject,
                confirmed=link.confirmed, linked_at=link.linked_at)
            tally.outcome(result, source_id, self.decisions)

    # --- 3. preferences ----------------------------------------------------------------

    def _preferences(self) -> None:
        tally = self.tally("preferences")
        for item in self.source.preferences():
            account = self.accounts.get(item.owner_id)
            if account is None:
                tally.misfit(item.owner_id, "dependency-not-migrated", self.decisions)
                continue
            if item.has_weights:
                # Interest weights have no v2 home; the settings themselves still move.
                tally.misfit(f"{item.owner_id}:interest-weights", "no-v2-home",
                             self.decisions, counted=False)
            defaults = {"personalization": item.enabled, "onboarded": item.onboarded}
            if item.summary_defaults:
                defaults["summary"] = item.summary_defaults
            if item.translation_defaults:
                defaults["translation"] = item.translation_defaults
            result = self.owners.settings.import_settings(
                account, appearance=APPEARANCE, language=LANGUAGE, defaults=defaults)
            tally.outcome(result, item.owner_id, self.decisions)

    # --- 4. papers -------------------------------------------------------------------------

    def _papers(self) -> None:
        from backend.modules.corpus.paper_import import TIME_REFUSED, LimitRecord, PaperSource

        tally, decisions = self.tally("paper"), self.decisions
        re_embed = decisions.maps("paper-embedding", "embedding-provenance-unproven")
        embeddings = self.tally("paper-embedding")
        # This run's own record of the corpus limits (L1-79), never added to another's.
        tally.limits = LimitRecord.of(self.owners.papers.limits)
        for paper in self.source.papers():
            self.boundary("paper")
            source_id = f"{paper.paper_id}:v{paper.version}"
            if source_id in self.skip_papers:
                tally.misfit(source_id, TIME_REFUSED, decisions)
                continue
            metadata = self.source.metadata(paper.paper_id, paper.version) or {}
            try:
                canonical = canonical_paper(arxiv=metadata.get("arxivId") or paper.paper_id,
                                            doi=metadata.get("doi"), key=paper.paper_id)
            except ValueError:
                tally.misfit(source_id, "ineligible-in-v2", decisions)
                continue
            if paper.figures:
                tally.misfit(source_id, "no-v2-home", decisions, kind="paper-figure",
                             counted=False)
            if self.source.embedded(paper.paper_id, paper.version):
                embeddings.misfit(source_id, "embedding-provenance-unproven", decisions)
            version = version_identity(canonical, paper.version)
            result, measure = self.owners.papers.import_measured(PaperSource(
                source_key=source_id, version=version, title=str(metadata.get("title") or ""),
                authors=tuple(metadata.get("authors") or ()),
                source_url=str(metadata.get("arxivUrl")
                               or f"https://arxiv.org/abs/{canonical.split(':', 1)[1]}"
                               f"v{paper.version}"),
                published_on=None, document=self.source.document(paper.doc_model_ref),
                metadata={"v1PaperId": paper.paper_id},
            ), re_embed=re_embed)
            tally.limits = tally.limits.add(measure)
            if tally.outcome(result, source_id, decisions):
                self.versions.setdefault(canonical, []).append((paper.version, version))

    # --- 5. saved papers -------------------------------------------------------------------

    def _saved_papers(self) -> None:
        tally, decisions = self.tally("saved-paper"), self.decisions
        seen: set[tuple[str, str]] = set()
        for item in self.source.saved():
            parts = arxiv_parts(item.arxiv_id)
            canonical = f"arxiv:{parts[0]}" if parts else None
            if canonical is None or item.owner_id not in self.accounts:
                tally.misfit(item.source_id, "dependency-not-migrated", decisions)
                continue
            if (item.owner_id, canonical) in seen:
                # Saved under another version suffix: collapsed into the first, reported.
                tally.misfit(item.source_id, "duplicate-by-version", decisions)
                continue
            seen.add((item.owner_id, canonical))
            versions = sorted(self.versions.get(canonical, ()))
            if not versions:
                tally.misfit(item.source_id, "dependency-not-migrated", decisions)
                continue
            result = self.owners.saved.import_saved_paper(
                self.accounts[item.owner_id], paper_id=canonical, version_id=versions[-1][1],
                saved_at=item.added_at)
            tally.outcome(result, item.source_id, decisions)

    # --- 6. what Q13 did not name ----------------------------------------------------------

    def _not_in_scope(self) -> None:
        for kind, sources in self.source.not_in_scope().items():
            tally = self.tally(kind)
            for source_id in sources:
                tally.misfit(source_id, NOT_IN_SCOPE, self.decisions)


# --- ops/bin/docsuri-migration-import ------------------------------------------------------

WORDS = ("import", "idempotency")
REFUSED_ENVIRONMENT = ("PYTHON", "DYLD_", "LD_")
MAX_INPUT = 64 * 1024
# The snapshot's two tar archives (the search index's documents and the objects with their
# manifests) follow the header line, streamed back in person by the operator tool.
MAX_PAYLOAD = 4 * 1024**3


def _emit(value: dict, status: int) -> int:
    sys.stdout.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
    sys.stdout.flush()
    return status


def main(argv: list[str] | None = None, *,
         run: Callable[[str, dict, bytes], dict] | None = None) -> int:
    """The fixed program's shape (D6): one word from its closed set, a bounded JSON header
    line on standard input and then the snapshot's archives, no caller-set interpreter
    variables, one JSON result. `run(word, header, archives)` is the composition's phase
    runner (production's: `docsuri_ops.production_wiring.production_import`)."""
    arguments = sys.argv[1:] if argv is None else argv
    if any(name.startswith(REFUSED_ENVIRONMENT) for name in os.environ):
        return _emit({"ok": False, "reason": "environment-refused"}, 2)
    if len(arguments) != 1 or arguments[0] not in WORDS:
        return _emit({"ok": False, "reason": "word-refused"}, 2)
    raw = sys.stdin.buffer.readline(MAX_INPUT + 1)
    try:
        document = json.loads(raw or b"{}")
    except ValueError:
        document = None
    if len(raw) > MAX_INPUT or not isinstance(document, dict):
        return _emit({"ok": False, "reason": "input-refused"}, 2)
    payload = sys.stdin.buffer.read(MAX_PAYLOAD + 1)
    if len(payload) > MAX_PAYLOAD:
        return _emit({"ok": False, "reason": "input-refused"}, 2)
    if run is None:
        return _emit({"ok": False, "reason": "import-runner-unbound"}, 1)
    import psycopg

    try:
        result = run(arguments[0], document, payload)
    except (ValueError, KeyError) as refused:
        return _emit({"ok": False, "reason": _reason(refused)}, 1)
    except (psycopg.Error, RuntimeError) as stopped:
        # A stopping error reaches the operator tool as a named reason (Step 68(h)).
        return _emit({"ok": False, "reason": _class_reason(stopped)}, 1)
    return _emit({"ok": True, **result}, 0)


def _reason(error: Exception) -> str:
    text = str(error.args[0]) if error.args else type(error).__name__
    return text if text.replace("-", "").isalnum() and len(text) <= 64 else "import-refused"


def _class_reason(error: Exception) -> str:
    """The error's class name in kebab case, at most 64 characters: `busy`,
    `operational-error`."""
    name = type(error).__name__
    text = "".join(f"-{char.lower()}" if char.isupper() and index else char.lower()
                   for index, char in enumerate(name))
    return text[:64]
