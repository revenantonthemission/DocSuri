"""F08 migration SSOT. Discovery checks completeness; it never selects executable SQL."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Explicit owner and ordered file list. Domain owners retain their SQL definitions.
DOMAINS = (
    (
        "accounts",
        "backend/modules/accounts/migrations",
        (
            "001_create_accounts_table.sql",
            "002_add_role_and_totp.sql",
            "003_create_lifecycle_tables.sql",
            "005_add_consent_columns.sql",
            "006_add_orcid_columns_to_social_identities.sql",
            "007_add_email_change_revoke_token.sql",
            "008_create_account_withdrawal_backups.sql",
            "009_make_email_nullable_for_orcid.sql",
            "010_make_withdrawal_backup_email_nullable.sql",
            "011_add_purge_attempts.sql",
            "012_drop_account_withdrawal_backups.sql",
            "013_block_late_writes_during_purge.sql",
        ),
    ),
    ("library", "backend/modules/library/migrations", ("001_create_library_tables.sql",)),
    (
        "personalization",
        "backend/modules/personalization/migrations",
        ("001_create_personalization_tables.sql",),
    ),
    ("onboarding", "backend/modules/onboarding/migrations", ("001_create_onboarding_status.sql",)),
    (
        "trends",
        "backend/modules/trends/migrations",
        ("001_create_trends_tables.sql", "002_unique_followed_topic_per_owner.sql"),
    ),
    ("plans", "backend/modules/plans/migrations", ("001_create_plans_tables.sql",)),
    ("mypage", "backend/modules/mypage/migrations", ("001_create_mypage_subscriptions.sql",)),
    (
        "research",
        "backend/modules/evidence/sessions/migrations",
        ("001_create_research_tables.sql", "002_add_resolved_paper_ids.sql"),
    ),
    (
        "novelty",
        "backend/modules/novelty/migrations",
        (
            "001_create_novelty_tables.sql",
            "002_create_novelty_messages.sql",
            "003_create_novelty_notion_connections.sql",
        ),
    ),
    ("evidence", "backend/modules/evidence/migrations", ("001_create_evidence_tables.sql",)),
    (
        "summarization",
        "backend/modules/summarization/migrations",
        ("001_create_user_glossary.sql",),
    ),
    (
        "ingestion",
        "ingestion/migrations/postgres",
        ("001_control_plane.sql", "002_paper_asset.sql", "003_corpus_control_plane.sql"),
    ),
)


@dataclass(frozen=True)
class MigrationDefinition:
    owner: str
    local_id: str
    path: Path
    digest: str

    @property
    def identity(self) -> str:
        return f"{self.owner}:{self.local_id}"


def registry(
    *, root: Path = ROOT, owners: set[str] | None = None
) -> tuple[MigrationDefinition, ...]:
    result = []
    root = root.resolve()
    known = {owner for owner, _, _ in DOMAINS}
    if owners is not None and not owners <= known:
        raise ValueError("unregistered migration owner")
    for owner, relative, files in DOMAINS:
        if owners is not None and owner not in owners:
            continue
        directory = (root / relative).resolve()
        if not directory.is_relative_to(root):
            raise ValueError("migration directory escapes root")
        discovered = {p.name for p in directory.glob("*.sql")}
        if discovered != set(files):
            raise ValueError(f"migration registry coverage mismatch: {owner}")
        for name in files:
            path = directory / name
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise ValueError("migration symlink not permitted")
            payload = path.read_bytes()
            result.append(
                MigrationDefinition(
                    owner, name, path, "sha256:" + hashlib.sha256(payload).hexdigest()
                )
            )
    if len({s.identity for s in result}) != len(result):
        raise ValueError("duplicate migration identity")
    return tuple(result)


def for_paths(paths: list[str | Path] | None) -> tuple[MigrationDefinition, ...]:
    if paths is None:
        return registry()
    resolved = {Path(p).resolve() for p in paths}
    directories = {(ROOT / relative).resolve(): owner for owner, relative, _ in DOMAINS}
    if not resolved <= directories.keys():
        raise ValueError("unregistered migration path")
    return registry(owners={directories[p] for p in resolved})
