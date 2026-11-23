"""The one composed migration chain of the complete v2 application (BR1.4, BR1.5).

The composed realm's runner (`scripts/verify_docsuri_u8.py`) and the production
environment tool both import `CHAIN` and apply it owner by owner, each file once, under
its owner's role. Applied files are never edited; a correction is a new file.

`CHAIN` is U1's base schemas and amendments, U2's control chain, then U3's, U4's, U5's
and U6's files and U8's own, each file once. Four pairs define the same object twice:

- `u2_controls.sql` and `u3_session_authority.sql` both add `accounts.session.purpose`
  and replace `accounts.guard_session`; U3's file would fail on the composed chain.
- `u2_controls.sql` and `u5_lifecycle_tables.sql` both create the lifecycle tables;
  U5's file mirrors U2's verbatim and would fail.
- `u2_capacity.sql` and `u3_capacity_v2.sql` both `CREATE FUNCTION
  operations.capacity_footprint()`; U3's would fail. `u3_capacity.sql` (its own name)
  and `u4_capacity.sql` (`CREATE OR REPLACE`) stay and apply in order.
- `local_login_receipts.sql` (U1) defines the entry receipt kinds a second time and
  `u2_controls.sql` drops the rule; neither can be left out.

Where the later file would fail, the chain leaves it out (`REPLACED`) and its owner's
reconciling file stands in its place, naming the replaced file in its first line. The
receipt kinds are restored by a reconciling file that replaces no file (`RECONCILES`).
A left-out file stays applied, unchanged, in its own unit's realm. See the approved
plan, decision "One composed migration chain":
`aidlc/spaces/default/intents/261016-finish-v2-rebuild/construction/u8-service-operations-integration/code-generation/code-generation-plan.md`.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# U1's base: one schema file per owner, installed by the base install before any chain
# file (the runner's `install_base`, the production tool's first step).
BASE: tuple[tuple[str, str], ...] = (
    ("accounts", "backend/modules/accounts/local_schema.sql"),
    ("corpus", "backend/modules/corpus/local_schema.sql"),
    ("library", "backend/modules/library/local_schema.sql"),
    ("personalization", "backend/modules/personalization/local_schema.sql"),
    ("discovery", "backend/modules/discovery/local_schema.sql"),
    ("usage", "backend/modules/plans/local_schema.sql"),
    ("assistance", "backend/modules/summarization/local_schema.sql"),
    ("operations", "ops/src/docsuri_ops/local_schema.sql"),
)

# U1's amendments, in U1's order (`scripts/bootstrap_docsuri_u1.py` AMENDMENTS; the
# runner refuses to migrate if the two lists ever differ).
U1_AMENDMENTS: tuple[tuple[str, str], ...] = (
    ("corpus", "backend/modules/corpus/local_binding_guards.sql"),
    ("assistance", "backend/modules/summarization/local_binding_guards.sql"),
    ("library", "backend/modules/library/local_operations.sql"),
    ("assistance", "backend/modules/summarization/local_glossary.sql"),
    ("corpus", "backend/modules/corpus/local_reference_guard.sql"),
    ("library", "backend/modules/library/local_reference_guard.sql"),
    ("accounts", "backend/modules/accounts/local_execution_guard.sql"),
    ("assistance", "backend/modules/summarization/local_claim_guards.sql"),
    ("accounts", "backend/modules/accounts/local_entry.sql"),
    ("corpus", "backend/modules/corpus/local_availability.sql"),
    ("corpus", "backend/modules/corpus/local_publication.sql"),
    ("usage", "backend/modules/plans/local_rejection.sql"),
    ("assistance", "backend/modules/summarization/local_admission_recovery.sql"),
    ("usage", "backend/modules/plans/local_rejection_grants.sql"),
    ("accounts", "backend/modules/accounts/local_execution_status.sql"),
    ("corpus", "backend/modules/corpus/local_execution_status.sql"),
    ("assistance", "backend/modules/summarization/local_execution_deadline.sql"),
    ("accounts", "backend/modules/accounts/local_login_receipts.sql"),
    ("corpus", "backend/modules/corpus/local_reference_metadata.sql"),
    ("library", "backend/modules/library/local_history_sequence.sql"),
    ("usage", "backend/modules/plans/local_period.sql"),
    ("assistance", "backend/modules/summarization/local_result_revision.sql"),
)

# U2's control chain, in U2's order (`scripts/verify_docsuri_u2.py` MIGRATIONS), ending
# with Discovery's U3 column file, which U2's realm carries too.
U2_CHAIN: tuple[tuple[str, str], ...] = (
    ("accounts", "backend/modules/accounts/u2_controls.sql"),
    ("personalization", "backend/modules/personalization/u2_controls.sql"),
    ("library", "backend/modules/library/u2_controls.sql"),
    ("usage", "backend/modules/plans/u2_controls.sql"),
    ("assistance", "backend/modules/summarization/u2_controls.sql"),
    ("accounts", "backend/modules/accounts/u2_consent_projection.sql"),
    ("accounts", "backend/modules/accounts/u2_personalization_status.sql"),
    ("corpus", "backend/modules/corpus/u2_personalization_read.sql"),
    ("personalization", "backend/modules/personalization/u2_cleanup_permissions.sql"),
    ("accounts", "backend/modules/accounts/u2_assignment_target.sql"),
    ("accounts", "backend/modules/accounts/u2_consent_obligation.sql"),
    ("accounts", "backend/modules/accounts/u2_personalization_effect.sql"),
    ("discovery", "backend/modules/discovery/u2_history_admission.sql"),
    ("library", "backend/modules/library/u2_history_binding.sql"),
    ("accounts", "backend/modules/accounts/u2_history_authority_grant.sql"),
    ("accounts", "backend/modules/accounts/u2_lifecycle_effect.sql"),
    ("accounts", "backend/modules/accounts/u2_lifecycle_action.sql"),
    ("accounts", "backend/modules/accounts/u2_lifecycle_owner_grants.sql"),
    ("library", "backend/modules/library/u2_erasure.sql"),
    ("personalization", "backend/modules/personalization/u2_erasure.sql"),
    ("accounts", "backend/modules/accounts/u2_consent_time.sql"),
    ("accounts", "backend/modules/accounts/u2_reset_confirmation.sql"),
    ("accounts", "backend/modules/accounts/u2_owner_cleanup.sql"),
    ("discovery", "backend/modules/discovery/u2_owner_cleanup.sql"),
    ("assistance", "backend/modules/summarization/u2_owner_cleanup.sql"),
    ("accounts", "backend/modules/accounts/u2_assistance_consent.sql"),
    ("assistance", "backend/modules/summarization/u2_consent_evidence.sql"),
    ("library", "backend/modules/library/u2_restore.sql"),
    ("personalization", "backend/modules/personalization/u2_restore.sql"),
    ("operations", "ops/src/docsuri_ops/u2_restore_checkpoint.sql"),
    ("accounts", "backend/modules/accounts/u2_restore.sql"),
    ("usage", "backend/modules/plans/u2_restore.sql"),
    ("assistance", "backend/modules/summarization/u2_restore.sql"),
    ("discovery", "backend/modules/discovery/u2_restore.sql"),
    ("accounts", "backend/modules/accounts/u2_restore_binding.sql"),
    ("usage", "backend/modules/plans/u2_restore_binding.sql"),
    ("assistance", "backend/modules/summarization/u2_restore_binding.sql"),
    ("discovery", "backend/modules/discovery/u2_restore_binding.sql"),
    ("accounts", "backend/modules/accounts/u2_restore_baseline.sql"),
    ("usage", "backend/modules/plans/u2_restore_baseline.sql"),
    ("assistance", "backend/modules/summarization/u2_restore_baseline.sql"),
    ("discovery", "backend/modules/discovery/u2_restore_baseline.sql"),
    ("library", "backend/modules/library/u2_restore_baseline.sql"),
    ("personalization", "backend/modules/personalization/u2_restore_baseline.sql"),
    ("assistance", "backend/modules/summarization/u2_restore_erasure.sql"),
    ("discovery", "backend/modules/discovery/u2_restore_erasure.sql"),
    ("operations", "ops/src/docsuri_ops/u2_capacity.sql"),
    ("operations", "ops/src/docsuri_ops/u2_capacity_database.sql"),
    ("discovery", "backend/modules/discovery/u3_schema.sql"),
)

# U3's to U6's files in U6's applied order, without the files U2's chain already holds,
# each left-out file replaced in place by its reconciling file.
LATER_UNITS: tuple[tuple[str, str], ...] = (
    ("accounts", "backend/modules/accounts/u8_receipt_kinds.sql"),
    ("corpus", "backend/modules/corpus/u3_schema.sql"),
    ("corpus", "backend/modules/corpus/u3_guards.sql"),
    ("corpus", "backend/modules/corpus/u3_watermark_v2.sql"),
    ("discovery", "backend/modules/discovery/u3_grants.sql"),
    ("library", "backend/modules/library/u3_schema.sql"),
    ("assistance", "backend/modules/summarization/u3_schema.sql"),
    ("assistance", "backend/modules/summarization/u3_glossary_v2.sql"),
    ("accounts", "backend/modules/accounts/u3_corpus_authority.sql"),
    ("accounts", "backend/modules/accounts/u8_session_authority.sql"),
    ("operations", "ops/src/docsuri_ops/u3_capacity.sql"),
    ("operations", "ops/src/docsuri_ops/u4_capacity.sql"),
    ("research", "backend/modules/research/u4_schema.sql"),
    ("research", "backend/modules/research/u4_admission.sql"),
    ("research", "backend/modules/research/u4_release_obligation.sql"),
    ("research", "backend/modules/research/u4_prepared_recovery.sql"),
    ("accounts", "backend/modules/accounts/u8_lifecycle_tables.sql"),
    ("accounts", "backend/modules/accounts/u5_lifecycle_guard.sql"),
    ("corpus", "backend/modules/corpus/u5_digest_read.sql"),
    ("accounts", "backend/modules/accounts/u5_digest_recipient.sql"),
    ("topics", "backend/modules/topics/u5_schema.sql"),
    ("topics", "backend/modules/topics/u5_erasure.sql"),
    ("topics", "backend/modules/topics/u5_run_guard.sql"),
    ("personalization", "backend/modules/personalization/u5_digest_preferences.sql"),
    ("topics", "backend/modules/topics/u5_preference_snapshot.sql"),
    ("topics", "backend/modules/topics/u5_schedule.sql"),
    ("topics", "backend/modules/topics/u5_unsubscribe_capability.sql"),
    ("topics", "backend/modules/topics/u5_real_send_retention.sql"),
    ("topics", "backend/modules/topics/u5_refusal_detail.sql"),
    # Added by U5's Build and Test loop-back 4 (2026-11-22): each run's scheduled
    # instant. Inserted here, in U6's applied order, not appended, so a realm migrated
    # before it is set up fresh, never migrated in place.
    ("topics", "backend/modules/topics/u5_scheduled_instant.sql"),
    ("accounts", "backend/modules/accounts/u6_lifecycle_guard.sql"),
    ("export", "backend/modules/export/u6_schema.sql"),
    ("export", "backend/modules/export/u6_custody.sql"),
    ("export", "backend/modules/export/u6_maintenance.sql"),
)

# U8's own owner migrations, then A10's capacity definition; Build and Test loop-back 1's
# files follow the capacity definition, appended so that every earlier realm's applied
# files stay a prefix of the chain.
U8_FILES: tuple[tuple[str, str], ...] = (
    ("accounts", "backend/modules/accounts/u8_accounts.sql"),
    # A correction added in Step 17: ServiceOperations' login reaches the lifecycle
    # guard only with USAGE on the accounts schema.
    ("accounts", "backend/modules/accounts/u8_operations_lifecycle.sql"),
    # A correction added in Step 17 (your decision of 2026-10-22, BR2.5): the date a
    # part retained by policy is gone, kept beside the scope's evidence.
    ("accounts", "backend/modules/accounts/u8_lifecycle_retention.sql"),
    # By your decision of 2026-10-25 ("Cap per address, raise site cap"): the keyed
    # address digest of an unfinished anonymous provider sign-in.
    ("accounts", "backend/modules/accounts/u8_identity_flow_address.sql"),
    # A correction added in the review fix of 2026-10-25: the digest is kept only while
    # it is counted (security-design § 3.2).
    ("accounts", "backend/modules/accounts/u8_identity_flow_address_release.sql"),
    # By your decision of 2026-10-25 ("Count every start, free places at once"): every
    # start counts under its address digest until its flow is deleted, a minute after it
    # expires, by AccountAccess's definer function.
    ("accounts", "backend/modules/accounts/u8_identity_flow_starts.sql"),
    ("research", "backend/modules/research/u8_research.sql"),
    # A correction added in Step 7: A2's updatedAt had no source column.
    ("research", "backend/modules/research/u8_research_job_times.sql"),
    # A correction added in Step 17: the runtime login cannot delete research's
    # records, so the participant's erasure needs this owner's definer function.
    ("research", "backend/modules/research/u8_research_erasure.sql"),
    # By your decision of 2026-10-24 (the research executor): the wait reason of a job
    # whose model runtime did not answer.
    ("research", "backend/modules/research/u8_research_waits.sql"),
    # By your decision of 2026-10-24 ("Until deleted or erased"): production's research
    # results are kept until deleted or erased, never ended by time.
    ("research", "backend/modules/research/u8_research_retention.sql"),
    ("assistance", "backend/modules/summarization/u8_assistance.sql"),
    # By the person's decision of 2026-10-23 ("Grant migrated accounts"): an entitlement
    # may carry the complete realms' control policies.
    ("usage", "backend/modules/plans/u8_entitlement_policy.sql"),
    ("export", "backend/modules/export/u8_export.sql"),
    ("corpus", "backend/modules/corpus/u8_search.sql"),
    ("operations", "ops/src/docsuri_ops/u8_operations.sql"),
    ("operations", "ops/src/docsuri_ops/u8_capacity.sql"),
    # Build and Test loop-back 1 (NFR9.7): PaperAssistance's job times, which the models
    # producer counts failed jobs by.
    ("assistance", "backend/modules/summarization/u8_assistance_job_times.sql"),
    # By your decision of 2026-11-01 ("Database default and U8 hooks", L1-6): each
    # origin_request_id defaults to the request identifier its transaction carries.
    ("research", "backend/modules/research/u8_research_request_origin.sql"),
    ("assistance", "backend/modules/summarization/u8_assistance_request_origin.sql"),
    ("export", "backend/modules/export/u8_export_request_origin.sql"),
    ("accounts", "backend/modules/accounts/u8_lifecycle_request_origin.sql"),
    # Build and Test loop-back 1 (NFR9.2): the observations a full buffer dropped.
    ("operations", "ops/src/docsuri_ops/u8_observation_drops.sql"),
    # By your answers of 2026-11-02 and 2026-11-08 (L1-69 "Send from an outbox", L1-71
    # "Check first and cap daily"): the outbox of the four signed-out mail requests, the
    # sender's beat and the count of account emails per account a UTC day.
    ("accounts", "backend/modules/accounts/u8_mail_outbox.sql"),
    # By your answer of 2026-11-11 on build batch 7's review ("Wire the owner read"):
    # ApprovedExport's definer function answering a Notion connection's owning account,
    # executable by ServiceOperations' login alone, for ProviderActivation's recipients.
    ("export", "backend/modules/export/u8_export_connection_owner.sql"),
)

CHAIN: tuple[tuple[str, str], ...] = BASE + U1_AMENDMENTS + U2_CHAIN + LATER_UNITS + U8_FILES

# The files the base install applies before the chain runs (the runner's `install_base`
# and U1's `amend`); the chain proper starts after them.
BASE_INSTALLED = frozenset(file for _, file in BASE + U1_AMENDMENTS)

# Left-out file -> its reconciling file (decision "One composed migration chain").
REPLACED: dict[str, str] = {
    "backend/modules/accounts/u3_session_authority.sql": (
        "backend/modules/accounts/u8_session_authority.sql"
    ),
    "backend/modules/accounts/u5_lifecycle_tables.sql": (
        "backend/modules/accounts/u8_lifecycle_tables.sql"
    ),
    "ops/src/docsuri_ops/u3_capacity_v2.sql": "ops/src/docsuri_ops/u8_capacity.sql",
}

# A reconciling file that replaces no file -> the files whose definitions it reconciles.
RECONCILES: dict[str, tuple[str, ...]] = {
    "backend/modules/accounts/u8_receipt_kinds.sql": (
        "backend/modules/accounts/local_login_receipts.sql",
        "backend/modules/accounts/u2_controls.sql",
    ),
}

# Before any of these files the applier grants the non-login operations schema owner
# CONNECT on the database and EXECUTE on pg_ls_waldir(), as U2's and U3's runners do.
CAPACITY_FILES = frozenset({
    "ops/src/docsuri_ops/u2_capacity.sql",
    "ops/src/docsuri_ops/u2_capacity_database.sql",
    "ops/src/docsuri_ops/u3_capacity.sql",
    "ops/src/docsuri_ops/u4_capacity.sql",
    "ops/src/docsuri_ops/u8_capacity.sql",
})

# The one definition each reconciled object reads back with after migration.
SESSION_PURPOSES = (
    "full_session", "primary_mfa_continuation", "reactivation_status",
    "preauthentication", "mfa", "proof", "consent_pending",
)
GUARD_PURPOSES = ("local-research", "personalization", "account-control", "administration")
RECEIPT_KINDS = ("register", "verification", "login", "password-reset", "reactivation")
LIFECYCLE_PARTICIPANT_ROLES = {
    "AccountAccess": "docsuri_accounts", "Library": "docsuri_library",
    "Personalization": "docsuri_personalization", "UsageEntitlements": "docsuri_usage",
    "PaperAssistance": "docsuri_assistance", "DiscoveryCitations": "docsuri_discovery",
    "ServiceOperations": "docsuri_operations", "TopicsDigests": "docsuri_topics",
    "ApprovedExport": "docsuri_export", "ResearchWorkspace": "docsuri_research",
}


def chain_files() -> tuple[str, ...]:
    """Every file of the chain, in order."""
    return tuple(file for _, file in CHAIN)


def migrations() -> tuple[tuple[str, str], ...]:
    """The chain after the base install: what an applier runs file by file."""
    return tuple(entry for entry in CHAIN if entry[1] not in BASE_INSTALLED)


def file_digest(relative: str, root: Path = ROOT) -> str:
    return hashlib.sha256((root / relative).read_bytes()).hexdigest()


def applied_difference(known: dict, root: Path = ROOT) -> list[str]:
    """The start's schema check (Workflow 1 step 3): every name where the database's
    applied digests differ from the chain, sorted. A chain file that is missing or holds
    another digest is named, and so is an applied file the chain does not list (a
    left-out file included). The base schemas are recorded under their owner's name.
    Nothing is migrated: an empty answer is the only one that lets the start continue."""
    base_files = {file for _, file in BASE}
    expected = {owner: file_digest(file, root) for owner, file in BASE}
    expected |= {file: file_digest(file, root) for _, file in CHAIN if file not in base_files}
    names = set(expected) | set(known)
    return sorted(name for name in names if known.get(name) != expected.get(name))
