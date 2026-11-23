"""Every operating value of U8's requirements, each tied to the row it comes from.

`PRODUCTION_OPERATIONS` holds exactly the approved rows; a test compares each field
with its row. `SYNTHETIC_OPERATIONS` shortens the times for the composed realm's
tests. The production profile accepts only `PRODUCTION_OPERATIONS` and every synthetic
profile refuses it (`require_policy`). The account policy's values stay with
AccountAccess and the corpus limits with CorpusContent, each selected by the profile.

Source abbreviations: OD = nfr-design/observability-design.md, RD = reliability-design.md,
SD = scalability-design.md, PD = performance-design.md, SecD = security-design.md,
NFR = nfr-requirements/security-requirements.md. See the approved plan:
`aidlc/spaces/default/intents/261016-finish-v2-rebuild/construction/u8-service-operations-integration/code-generation/code-generation-plan.md`
(Step 1, `backend/u8_policy.py`).
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass

MINUTE = 60
HOUR = 60 * MINUTE
DAY = 24 * HOUR
MIB = 1024**2
GIB = 1024**3

# Ollama's "never unload" keep-alive. It is a sentinel, not a duration, so it is the one
# numeric field `__post_init__` checks for exactly this value instead of for finite and
# positive (PD § 3.3, "Every embedding call v2 makes passes `keep_alive: -1`").
KEEP_ALIVE_FOREVER = -1

# PD § 10: the fixed list of route classes.
ROUTE_CLASSES = (
    "health", "navigation", "read", "search", "accept", "stream", "asset", "static",
    "administration",
)


@dataclass(frozen=True)
class OperationsPolicy:
    """U8's operating values. Durations are seconds, sizes bytes, limits counts."""

    name: str

    # --- Observations -------------------------------------------------------------
    # OD § 3.2 row "Required ...": renewal 60 s, stale after 180 s, incident at once
    # when unavailable and after 10 minutes degraded, unknown or stale.
    required_renewal_seconds: int = 60
    required_stale_seconds: int = 180
    required_incident_seconds: int = 10 * MINUTE
    # OD § 3.2 row "Providers and platform.status": renewal 5 minutes, stale 15 minutes.
    provider_renewal_seconds: int = 5 * MINUTE
    provider_stale_seconds: int = 15 * MINUTE
    # OD § 3.2 row "operations.cutover": 5 minutes, 15 minutes, incident after 15 minutes.
    cutover_renewal_seconds: int = 5 * MINUTE
    cutover_stale_seconds: int = 15 * MINUTE
    cutover_incident_seconds: int = 15 * MINUTE
    # OD § 3.2 row "platform.isolation": 5 minutes, 15 minutes, incident after 15 minutes.
    isolation_renewal_seconds: int = 5 * MINUTE
    isolation_stale_seconds: int = 15 * MINUTE
    isolation_incident_seconds: int = 15 * MINUTE
    # OD § 3.1 "Bounded buffering": up to 60 observations held in memory.
    observation_buffer: int = 60
    # OD § 3.1 "Housekeeping": observations older than 14 days are deleted.
    observation_retention_seconds: int = 14 * DAY
    # OD § 4 "운영": refreshes every 30 seconds.
    dashboard_refresh_seconds: int = 30
    # OD § 4 "작업": the list refreshes every 5 seconds while a job is unfinished.
    job_list_refresh_seconds: int = 5
    # OD § 3.2 "Export": degraded once its oldest unclear or accepted effect is > 24 h.
    export_degraded_after_seconds: int = 24 * HOUR
    # OD § 3.2 "Digests": degraded once the oldest pending delivery is 2 h late.
    digest_late_seconds: int = 2 * HOUR
    # OD § 3.2 "Error rates": failed over terminal effects in the last 24 hours.
    error_rate_window_seconds: int = 24 * HOUR

    # --- Backups and restores -----------------------------------------------------
    # RD § 6 "The daily run, at 04:00 Asia/Seoul".
    backup_hour_seoul: int = 4
    # RD § 7 "Every Sunday at 05:00" (Python weekday: Sunday is 6).
    verification_hour_seoul: int = 5
    verification_weekday: int = 6
    # RD § 6 "Catch-up (R4)": runs a missed backup if the newest passed set is > 24 h.
    backup_catch_up_seconds: int = 24 * HOUR
    # RD § 6 "Retention": daily sets 14 days, Sunday's 8 weeks.
    daily_set_retention_seconds: int = 14 * DAY
    sunday_set_retention_seconds: int = 8 * 7 * DAY
    # RD § 7 "The bound applies to the start": within 24 h of its tombstone, completing
    # within 60 minutes of that start.
    erasure_verification_start_seconds: int = 24 * HOUR
    verification_completion_seconds: int = 60 * MINUTE
    # RD § 8 table: 5, 25, 45, 10, 25 and 10 minutes, inside 2 hours.
    restore_route_and_stop_seconds: int = 5 * MINUTE
    restore_pre_backup_seconds: int = 25 * MINUTE
    restore_recreate_and_restore_seconds: int = 45 * MINUTE
    restore_replay_and_integrity_seconds: int = 10 * MINUTE
    restore_post_backup_seconds: int = 25 * MINUTE
    restore_start_and_route_seconds: int = 10 * MINUTE
    restore_total_seconds: int = 2 * HOUR
    # RD § 8 "Request expiry (NFR7.10)": not admitted or not started within 24 hours.
    recovery_start_seconds: int = 24 * HOUR

    # --- Storage --------------------------------------------------------------------
    # SD § 3.2: the 8 GiB budget, degraded from 80%, unavailable from 8 GiB less 256 MiB.
    footprint_budget_bytes: int = 8 * GIB
    footprint_warning_ratio: float = 0.8
    footprint_headroom_bytes: int = 256 * MIB
    # SD § 3.3: degraded below 20 GiB free, unavailable below the 10 GiB critical floor.
    internal_disk_threshold_bytes: int = 20 * GIB
    internal_disk_critical_bytes: int = 10 * GIB
    # SD § 3.3 "What a run will write": 4 GiB before the first accepted dry run.
    first_rehearsal_estimate_bytes: int = 4 * GIB
    # SD § 3.4: production, two rehearsal, one import, one scratch database at once.
    production_databases: int = 1
    rehearsal_databases: int = 2
    import_databases: int = 1
    scratch_databases: int = 1
    # SD § 4 "The backup floor": 64 GiB on the backup volume.
    backup_volume_floor_bytes: int = 64 * GIB

    # --- Retained copies (NFR3.12's table, NFR3.13, SecD § 6.7) ---------------------
    # "A dry run's copy of v1": disposed when its run ends; backstop 14 days.
    dry_run_copy_backstop_seconds: int = 14 * DAY
    # "An import database": disposed when its run ends; backstop 14 days.
    import_database_backstop_seconds: int = 14 * DAY
    # "A rehearsal database, with its backup sets": backstop 60 days after creation.
    rehearsal_database_backstop_seconds: int = 60 * DAY
    # "A scratch restore a failed check left behind": backstop 1 day.
    scratch_restore_backstop_seconds: int = 1 * DAY
    # "The v1 final snapshot": 30 days after settlement or abort; backstop 120 days.
    final_snapshot_disposal_seconds: int = 30 * DAY
    final_snapshot_backstop_seconds: int = 120 * DAY
    # "v1's stores": 90 days after admission opens; backstop 180 days.
    v1_stores_disposal_seconds: int = 90 * DAY
    v1_stores_backstop_seconds: int = 180 * DAY
    # "A rolled-back v2 database": 30 days after the rollback; backstop 90 days.
    rolled_back_disposal_seconds: int = 30 * DAY
    rolled_back_backstop_seconds: int = 90 * DAY
    # "A staging file on the backup volume": when its write ends; backstop 1 day.
    staging_file_backstop_seconds: int = 1 * DAY
    # NFR3.13: a decided date earlier than 14 days after the copy was written is refused.
    decided_date_minimum_seconds: int = 14 * DAY
    # SecD § 6.7: internal-disk copies' dates carry +24 hours for local snapshots.
    internal_disk_tail_seconds: int = 24 * HOUR

    # --- Email (SecD § 13) ------------------------------------------------------------
    # A digest only while the UTC day's count of all mail is below 60; account mail
    # below 90; nothing once the UTC month's count reaches 2,700.
    digest_daily_limit: int = 60
    account_mail_daily_limit: int = 90
    mail_monthly_limit: int = 2700

    # --- Cutover (RD § 12) ------------------------------------------------------------
    # NFR7.14: a soak of 7 days clean; v1's restart rehearsal within 7 days; a consumer
    # inventory covering 14 days; isolation evidence passed within 15 minutes.
    soak_clean_seconds: int = 7 * DAY
    restart_rehearsal_seconds: int = 7 * DAY
    consumer_window_seconds: int = 14 * DAY
    # The inventory's window ends within 24 hours before the switch's check: your
    # decision of 2026-11-01 (L1-21, "Within 24 h of the switch"); RD § 12 names only
    # the 14 days it covers.
    inventory_recency_seconds: int = 24 * HOUR
    isolation_freshness_seconds: int = 15 * MINUTE
    # NFR7.15: the 4-hour bound from v1's stop.
    switch_bound_seconds: int = 4 * HOUR
    # NFR7.16: a rollback is possible for 14 days after admission opens.
    rollback_window_seconds: int = 14 * DAY

    # --- Arrangement ------------------------------------------------------------------
    # The plan's "Arrangement" row: a stop record is bounded at 14 days (SecD § 6.8).
    stop_record_bound_seconds: int = 14 * DAY
    # OD § 12 / RD § 11: one availability slot every 5 minutes; each probe within 10 s.
    availability_slot_seconds: int = 5 * MINUTE
    probe_limit_seconds: int = 10
    # OD § 12 "Retention": files older than 13 months are deleted.
    availability_retention_months: int = 13
    # OD § 13 / PD § 10: 5-minute latency summaries, kept 14 days.
    latency_window_seconds: int = 5 * MINUTE
    latency_retention_seconds: int = 14 * DAY
    # PD § 10 "Route classes": the fixed list.
    route_classes: tuple[str, ...] = ROUTE_CLASSES

    # --- Model runtime (PD § 3.3) -----------------------------------------------------
    # Every embedding call passes `keep_alive: -1`; the search probe re-pins every 60 s.
    search_model_keep_alive: int = KEEP_ALIVE_FOREVER
    search_model_repin_seconds: int = 60
    # PD § 2.4 / A7: the query's embedding is bounded at 2 s, then search answers by words.
    embedding_bound_seconds: float = 2.0
    # PD § 3.3 "Imports": batches of 16 paragraph-sized chunks.
    embedding_batch_chunks: int = 16
    # PD § 3.3 "One model job at a time": a lane of one.
    model_job_lane: int = 1
    # PD § 3.3, the research model (U8 plan Step 1's "Model runtime" line; your decision of
    # 2026-10-24, "Build the research executor"): qwen3:8b loads when a job needs it and
    # unloads after 5 idle minutes, so it never holds memory beside the search model.
    research_model_keep_alive_seconds: int = 300

    # --- Connection gates (PD § 3.1) --------------------------------------------------
    host_connections: int = 12
    worker_connections: int = 8
    observation_connections: int = 2
    maintenance_connections: int = 2
    scheduler_connections: int = 3
    backup_agent_connections: int = 3
    operator_tool_connections: int = 2
    migration_tool_connections: int = 4

    def __post_init__(self) -> None:
        if self.name not in ("production", "synthetic"):
            raise ValueError("operations policy name must be production or synthetic")
        if (
            not self.route_classes
            or len(set(self.route_classes)) != len(self.route_classes)
            or not all(isinstance(item, str) and item for item in self.route_classes)
        ):
            raise ValueError("route classes must be distinct non-empty names")
        for field in dataclasses.fields(self):
            if field.name in ("name", "route_classes"):
                continue
            value = getattr(self, field.name)
            if field.name == "search_model_keep_alive":
                if type(value) is not int or value != KEEP_ALIVE_FOREVER:
                    raise ValueError("search_model_keep_alive must be Ollama's -1 sentinel")
                continue
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{field.name} must be finite and positive")
        if not 0 < self.footprint_warning_ratio < 1:
            raise ValueError("footprint_warning_ratio must lie strictly between 0 and 1")
        if self.footprint_headroom_bytes >= self.footprint_budget_bytes:
            raise ValueError("the footprint headroom must be below the budget")
        if self.internal_disk_critical_bytes >= self.internal_disk_threshold_bytes:
            raise ValueError("the critical floor must lie below the threshold")
        if not self.digest_daily_limit <= self.account_mail_daily_limit <= self.mail_monthly_limit:
            raise ValueError("email limits must nest: digests, account mail, month")
        steps = (
            self.restore_route_and_stop_seconds
            + self.restore_pre_backup_seconds
            + self.restore_recreate_and_restore_seconds
            + self.restore_replay_and_integrity_seconds
            + self.restore_post_backup_seconds
            + self.restore_start_and_route_seconds
        )
        if steps > self.restore_total_seconds:
            raise ValueError("the restore step bounds must fit inside the restore total")


PRODUCTION_OPERATIONS = OperationsPolicy(name="production")

# The composed realm's tests: the same shape with shortened times. Counts, sizes,
# limits and gates are unchanged, so every bound the tests prove is the real one.
SYNTHETIC_OPERATIONS = dataclasses.replace(
    PRODUCTION_OPERATIONS,
    name="synthetic",
    required_renewal_seconds=2,
    required_stale_seconds=6,
    required_incident_seconds=20,
    provider_renewal_seconds=5,
    provider_stale_seconds=15,
    cutover_renewal_seconds=5,
    cutover_stale_seconds=15,
    cutover_incident_seconds=15,
    isolation_renewal_seconds=5,
    isolation_stale_seconds=15,
    isolation_incident_seconds=15,
    dashboard_refresh_seconds=2,
    job_list_refresh_seconds=1,
    search_model_repin_seconds=5,
    restore_route_and_stop_seconds=5,
    restore_pre_backup_seconds=25,
    restore_recreate_and_restore_seconds=45,
    restore_replay_and_integrity_seconds=10,
    restore_post_backup_seconds=25,
    restore_start_and_route_seconds=10,
    restore_total_seconds=120,
    verification_completion_seconds=60,
    availability_slot_seconds=5,
    probe_limit_seconds=2,
    latency_window_seconds=5,
)


def require_policy(policy: OperationsPolicy, *, production: bool) -> OperationsPolicy:
    """The production profile accepts only `PRODUCTION_OPERATIONS`; every synthetic
    profile refuses it and accepts only `SYNTHETIC_OPERATIONS`."""
    expected = PRODUCTION_OPERATIONS if production else SYNTHETIC_OPERATIONS
    if policy != expected:
        raise ValueError(
            "the production profile accepts only the production operations policy"
            if production
            else "a synthetic profile refuses the production operations policy"
        )
    return policy
