"""The required items and the test, phase or boundaries row each rests on (U8 plan Step
96(g)): a data module beside `built_files.py`, which `operations/test_required_items.py`
checks (Step 98(b)) through `lane_map.py`.

One entry per bullet of:

- security-design.md § 15 (48 bullets);
- its amendment in the code summary, "Provider sign-in starts" (8 bullets);
- security-requirements.md § Required verification (13 bullets);
- cicd-pipeline.md § 11 (20 bullets);
- BR10.3's journeys, written here as literals: J01–J14 with their names, A11Y and SEC;
- NFR8.1–NFR8.12.

Each section's text is pinned by its SHA-256, and so are BR10.3's and BR10.6's texts. A
section's text is its bullet block: from the first line starting `- ` after the section's
heading, every following line that starts with `- ` or with a space, each with its newline.
A bullet is counted when it is a leaf (no deeper bullet follows it). A rule's text is its
YAML item: from its `  - id:` line to the line before the next one, trailing blank lines
dropped, each line with its newline.

Each entry is keyed by source, group and position (`security-design-15/D3/4`); an item
split by clause (L1-59) adds the clause's name (`nfr8/NFR8.6/crashed-host`). Each entry
names exactly one of:

- `pytest`: a node, `<path>::<function>`, the path from the repository's root;
- `playwright`: a spec under `frontend/e2e/u8-complete` and a title tagged `[Jxx]`,
  `[SEC]`, `[A11Y]` or `[PERF]`;
- `vitest`: a file under `frontend/test/u8-complete` and a test's title;
- `row`: the first cell of a row of the plan's "Completion and evidence boundaries", for a
  clause only a later stage can show;
- `phase`: for NFR8.6's two crash clauses only, `restart-host` or `restart-database`.

The D3 entries name the security spec's titles as Step 100 leaves them: the module's
check first runs after Step 103 (Step 98(f)).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECORD = "aidlc/spaces/default/intents/261016-finish-v2-rebuild/construction/" \
    "u8-service-operations-integration"
T = "tests/u8_service_operations_integration"
SPECS = "frontend/e2e/u8-complete"
VITEST = "frontend/test/u8-complete"


# --- the sections and their pins --------------------------------------------------------------


def bullet_block(text: str, heading: str) -> str:
    """The bullet block after `heading` (an exact line), as the module's docstring says."""
    lines = text.splitlines(keepends=True)
    start = next(index for index, line in enumerate(lines) if line.rstrip("\n") == heading)
    first = next(index for index in range(start + 1, len(lines))
                 if lines[index].startswith("- "))
    block = []
    for line in lines[first:]:
        if not (line.startswith("- ") or line.startswith(" ")) or not line.strip():
            break
        block.append(line)
    return "".join(block)


def leaf_count(block: str) -> int:
    """The bullets of a block that no deeper bullet follows."""
    bullets = [line for line in block.splitlines() if line.lstrip().startswith("- ")]
    depths = [len(line) - len(line.lstrip()) for line in bullets]
    return sum(1 for index, depth in enumerate(depths)
               if index + 1 == len(depths) or depths[index + 1] <= depth)


def rule_text(text: str, rule: str) -> str:
    """A rule's YAML item in rules.md, as the module's docstring says."""
    lines = text.splitlines(keepends=True)
    start = next(index for index, line in enumerate(lines)
                 if line.rstrip("\n") == f"  - id: {rule}")
    end = next((index for index in range(start + 1, len(lines))
                if lines[index].startswith("  - id: ")), len(lines))
    item = lines[start:end]
    while item and not item[-1].strip():
        item.pop()
    return "".join(item)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


SECTIONS = {
    "security-design-15": {
        "path": f"{RECORD}/nfr-design/security-design.md",
        "heading": "## 15. Required verification",
        "bullets": 48,
        "sha256": "cae7d23b9fa13a0413487141a82e47cae9e2c5117e357c2d92f6764635fbe0e8",
    },
    "code-summary-starts": {
        "path": f"{RECORD}/code-generation/code-summary.md",
        "heading": "**§ 15, add:**",
        "bullets": 8,
        "sha256": "7eac5167de00921cbca168a5f7c8e4c144aa3b855f41977d49e71d789e4c6387",
    },
    "security-requirements": {
        "path": f"{RECORD}/nfr-requirements/security-requirements.md",
        "heading": "## Required verification",
        "bullets": 13,
        "sha256": "75c5084a9b146a48393cccae89462fc6852f594a56faef23a0d5ec00092facc8",
    },
    "cicd-pipeline-11": {
        "path": f"{RECORD}/infrastructure-design/cicd-pipeline.md",
        "heading": "## 11. Required verification",
        "bullets": 20,
        "sha256": "0f0288c9fdd6d8916199f8e4dfcadd7dc209e7f4f0560dcb58a50970b305b897",
    },
}
RULES = {
    "path": f"{RECORD}/functional-design/rules.md",
    "BR10.3": "62feaaa4c385a62d7f82b3ff5ea1214ee5963af47c1a1ffd85d2976606a66196",
    "BR10.6": "535af7d99abb6f2ee82b9eda645fe3cb301cbecc06cb3c07f7d92164d64cc0fa",
}

# BR10.3's journeys with their names, as `u8_phases.JOURNEYS` must hold them.
JOURNEYS = {
    "J01": "sign-in-library-search-paper-research-novelty-export",
    "J02": "topics-to-digest",
    "J03": "public-and-private-isolation",
    "J04": "current-authority",
    "J05": "late-effects",
    "J06": "drafts-switched-off",
    "J07": "job-lifecycle",
    "J08": "withdrawal-reactivation-erasure",
    "J09": "backup-and-restore-verification",
    "J10": "migration-of-the-synthetic-v1",
    "J11": "cutover-procedures",
    "J12": "navigation-states",
    "J13": "owner-isolation",
    "J14": "repair-exercise",
    "A11Y": "accessibility-of-the-complete-application",
    "SEC": "security-boundaries",
}

# --- the boundaries rows the entries name ------------------------------------------------------

ROW_IN_PERSON = ("In person (D4): two in-person commands each ask for the password; a cached "
                 "authentication runs none; `sudo -n true` fails afterwards; the scheduler can "
                 "run none; the same over SSH")
ROW_KEYCHAIN = ("D5's first item: your login account cannot read the operator tool's keychain "
                "items without your password")
ROW_SUDO = ("NFR1.5: real sudo refuses the service account every agent, operator and "
            "service-control command, and the scheduler every in-person and service-control "
            "command")
ROW_LISTENER = ("NFR3.3: a stand-in listener on 15432 completes no login; a TCP login as the "
                "superuser fails; a connection without SCRAM fails v2's start against the real "
                "instance")
ROW_PORTS = ("NFR3.8: another account's listener on 18200, 18201, 11434 or 15432 receives no "
             "connection, even while its service is stopped")
ROW_CLOUDFLARE = ("A forged `CF-Connecting-IP` through Cloudflare is counted under the real "
                  "address; the shell fetched through the public address equals the release's "
                  "build byte for byte; Cloudflare's hostname settings")
ROW_FIRST_RELEASE = ("The first release: `main`'s one-off push, `v2.0.0` through `custom_tag`, "
                     "the guard, the annotated tag; branch protection's required checks "
                     "reporting")
ROW_SCALE = ("NFR8.1–NFR8.5, and NFR8.12's 20 concurrent signed-in users, at the production "
             "scale on this Mac")
ROW_RESTART = ("NFR8.6 at the installation's authorized restart (Workflow 20 step 10) and at "
               "v1's restart rehearsal: at the installation, readiness within 3 minutes of the "
               "restarted jobs' start, PostgreSQL's start and crash recovery, the model "
               "runtime and the tunnel included; at the rehearsal, v1's own restart")
ROW_MEMORY = ("NFR8.7's memory clauses: v2's host and workers together under 4 GiB of "
              "resident memory at 20 concurrent users, the rest of the 24 GiB left for the "
              "model runtime with its two pinned models, v1 and macOS")
ROW_DRY_RUN = ("NFR8.8's 2 hours on real v1 data: a dry run within 2 hours, from its "
               "snapshot's start to its parity report, every paper embedded again")
ROW_BACKUP = ("NFR8.9 at the 8 GiB budget: a backup within 25 minutes, a restore into a "
              "database within 45 minutes, and a restore verification, with its checks and the "
              "scratch database's removal, within 60 minutes")
ROW_UPGRADE = ("NFR8.11's runtime upgrade: a PostgreSQL, Ollama, cloudflared or Python upgrade "
               "measured again against the six response targets before it reaches production")
ROW_COMPATIBILITY = ("The previous release's critical journeys on the candidate's schema, with "
                     "a real previous v2 release")


def _p(path: str, function: str) -> dict:
    return {"pytest": f"{T}/{path}::{function}"}


def _w(spec: str, title: str) -> dict:
    return {"playwright": (f"{SPECS}/{spec}", title)}


def _v(file: str, title: str) -> dict:
    return {"vitest": (f"{VITEST}/{file}", title)}


def _r(first_cell: str) -> dict:
    return {"row": first_cell}


SD = "security-design-15"
LIMITS = "integration/test_sign_in_limits.py"

ENTRIES: dict[str, dict] = {
    # security-design.md § 15 -- Policy (D1).
    f"{SD}/D1/1/lengths": _p("component/test_production_policy.py",
                             "test_each_session_takes_its_policys_length_from_the_injected_clock"),
    f"{SD}/D1/1/no-extension": _p("component/test_production_policy.py",
                                  "test_activity_extends_no_session"),
    f"{SD}/D1/2": _p("component/test_production_policy.py",
                     "test_a_member_with_a_second_factor_gets_the_members_length"),
    f"{SD}/D1/3": _p("component/test_production_policy.py",
                     "test_each_policy_refuses_the_other_realm"),
    f"{SD}/D1/4": _p("component/test_production_policy.py",
                     "test_the_cap_refuses_the_next_account_with_the_existing_answer"),
    # Sign-in limits (D2).
    f"{SD}/D2/1": _p(
        LIMITS, "test_the_21st_attempt_from_one_address_is_refused_before_any_password"),
    f"{SD}/D2/2": _p(LIMITS, "test_after_five_failures_an_email_waits_fifteen_minutes_with_or_"
                             "without_an_account"),
    f"{SD}/D2/3": _p(LIMITS, "test_the_121st_attempt_within_a_minute_is_refused_for_everyone"),
    f"{SD}/D2/4": _p(LIMITS, "test_one_address_flooding_leaves_a_second_able_to_sign_in_and_"
                             "refusals_count_nothing"),
    f"{SD}/D2/5": _p(LIMITS, "test_a_forged_connecting_address_through_the_standin_counts_under_"
                             "its_peer"),
    f"{SD}/D2/6": _p(LIMITS, "test_a_missing_or_malformed_header_lands_in_the_unknown_bucket"),
    f"{SD}/D2/7": _p(LIMITS, "test_two_ipv6_addresses_in_one_64_share_a_bucket"),
    f"{SD}/D2/8": _p(LIMITS, "test_no_address_or_email_appears_outside_its_keyed_digest"),
    # Arrivals from another site (D3), with the security spec's titles as Step 100 leaves them.
    f"{SD}/D3/1": _w("security.spec.ts",
                     "[SEC] a Google sign-in arrives back cross-site and signs the linked "
                     "account in"),
    f"{SD}/D3/2": _v("callback-page.test.tsx",
                     "removes the query with replaceState before it calls the API route"),
    f"{SD}/D3/3": _w("security.spec.ts",
                     "[SEC] an ORCID error return reads as cancelled and calls no identity "
                     "callback route"),
    # Your settled wording of 2026-11-01 (L1-1).
    f"{SD}/D3/4": {
        **_w("security.spec.ts",
             "[SEC] each email link opened in a fresh browser explains it and asks again "
             "here"),
        "wording": ("an email link opened in a fresh browser reaches its page, says on "
                    "arrival that it works only in the browser that asked, and after a "
                    "refused submit shows its kind's text and offers to ask again from this "
                    "browser"),
        "settled": "2026-11-01 (L1-1)",
    },
    # In person (D4): real sudo, at the installation.
    f"{SD}/D4/1": _r(ROW_IN_PERSON),
    f"{SD}/D4/2": _r(ROW_IN_PERSON),
    f"{SD}/D4/3": _r(ROW_IN_PERSON),
    f"{SD}/D4/4": _r(ROW_IN_PERSON),
    f"{SD}/D4/5": _r(ROW_IN_PERSON),
    # Credential release (D5).
    f"{SD}/D5/1": _r(ROW_KEYCHAIN),
    f"{SD}/D5/2": _p("operations/test_credential_release.py",
                     "test_the_released_password_is_used_by_one_connection_and_shows_nowhere"),
    # Fixed commands (D6).
    f"{SD}/D6/1": _p("operations/test_fixed_programs.py",
                     "test_each_installed_program_checks_its_environment_and_word_in_its_own_"
                     "process"),
    # Browser boundary (D7).
    f"{SD}/D7/1": _p("integration/test_boundary.py",
                     "test_a_request_through_the_standin_reaches_its_browser_route_as_https"),
    f"{SD}/D7/2": _p("integration/test_boundary.py",
                     "test_a_forged_forwarded_header_changes_neither_scheme_nor_client"),
    f"{SD}/D7/3": _p("integration/test_boundary.py",
                     "test_a_request_for_loopback_reaches_the_health_routes_and_no_browser_"
                     "route"),
    f"{SD}/D7/4": _p("integration/test_boundary.py",
                     "test_every_kind_of_answer_carries_the_literal_headers"),
    f"{SD}/D7/5": _p("integration/test_static_routes.py",
                     "test_only_content_hashed_files_are_cacheable_and_a_missing_document_"
                     "says_so"),
    f"{SD}/D7/6": _r(ROW_CLOUDFLARE),
    f"{SD}/D7/7": _p("integration/test_boundary.py",
                     "test_a_host_name_other_than_the_accepted_ones_is_refused"),
    # Logs (D11).
    f"{SD}/D11/1": _p("operations/test_logrotate_rules.py",
                      "test_a_linked_log_folder_and_a_linked_folder_above_it_are_skipped"),
    f"{SD}/D11/2": _p("operations/test_logrotate_rules.py",
                      "test_a_fifo_under_a_logs_name_is_skipped_at_once"),
    f"{SD}/D11/3": _p("operations/test_logrotate_rules.py", "test_a_hard_link_is_skipped"),
    f"{SD}/D11/4": _p("operations/test_logrotate_rules.py",
                      "test_a_moved_v2_log_loses_no_line_written_around_the_move"),
    f"{SD}/D11/5": _p("operations/test_logrotate_rules.py",
                      "test_copy_then_truncate_records_the_bytes_written_during_the_copy"),
    f"{SD}/D11/6": _p("arrangement/test_logrotate.py",
                      "test_no_copy_older_than_14_days_remains_and_each_keeps_owner_and_0600"),
    f"{SD}/D11/7": _p("component/test_log_events.py",
                      "test_an_unregistered_field_raises_when_synthetic_and_is_dropped_and_"
                      "counted_in_production"),
    # The extension (D14).
    f"{SD}/D14/1": _p("database/test_u8_schema.py",
                      "test_pgvector_is_in_template1_and_every_later_database"),
    f"{SD}/D14/2": _p("integration/test_backup_agent_restore.py",
                      "test_the_agents_login_restores_a_set_into_a_scratch_copy_the_disposable_"
                      "role_owns"),
    f"{SD}/D14/3": _p("integration/test_production_restore.py",
                      "test_the_full_path_records_every_receipt_and_keeps_every_owner"),
    f"{SD}/D14/4": _p("database/test_u8_schema.py",
                      "test_no_login_but_the_superuser_can_create_another_extension"),
    # Email allowance (D12).
    f"{SD}/D12/1": _p("component/test_allowance.py",
                      "test_the_61st_digest_of_a_utc_day_waits_while_account_mail_continues_"
                      "to_90"),
    f"{SD}/D12/2": _p("component/test_allowance.py", "test_at_2700_in_a_month_all_mail_stops"),
    f"{SD}/D12/3": _p("component/test_allowance.py",
                      "test_a_refused_send_releases_its_place_and_an_unknown_outcome_keeps_it"),
    f"{SD}/D12/4": _p("component/test_allowance.py",
                      "test_a_restore_of_the_database_leaves_the_count"),
    f"{SD}/D12/5": _p("component/test_allowance.py",
                      "test_a_retry_reuses_its_messages_key_and_reservation"),
    f"{SD}/D12/6": _p("operations/test_import_boundaries.py",
                      "test_no_module_of_accounts_or_topics_imports_service_operations"),
    # The amendment in the code summary: "Provider sign-in starts".
    "code-summary-starts/provider-starts/1": _p(
        LIMITS, "test_an_addresss_fourth_open_start_is_refused_writing_nothing_while_another_"
                "starts"),
    "code-summary-starts/provider-starts/2": _p(
        LIMITS, "test_completions_refused_after_the_answer_free_their_places_and_one_before_"
                "its_claim_does_not"),
    "code-summary-starts/provider-starts/3": _p(
        LIMITS, "test_ten_unfinished_starts_refuse_the_eleventh_and_thirty_in_all_refuse_the_"
                "thirty_first"),
    "code-summary-starts/provider-starts/4": _p(
        LIMITS, "test_three_64s_of_one_48_fill_its_places_while_d2_counts_each_64_apart"),
    "code-summary-starts/provider-starts/5": _p(
        LIMITS, "test_a_members_link_starts_count_under_the_account_and_under_the_address"),
    "code-summary-starts/provider-starts/6/open-flows": _p(
        LIMITS, "test_the_complete_realms_admit_the_200th_open_flow_and_refuse_the_201st_and_"
                "u2_keeps_20"),
    "code-summary-starts/provider-starts/6/starts": _p(
        LIMITS, "test_fresh_addresses_are_refused_once_the_site_counts_600_starts_within_5_"
                "minutes"),
    "code-summary-starts/provider-starts/7": _p(
        LIMITS, "test_the_deletion_pass_deletes_flows_a_minute_past_their_expiry_at_most_limit_"
                "at_a_time"),
    "code-summary-starts/provider-starts/8/d2": _p(
        LIMITS, "test_three_64s_of_one_48_fill_its_places_while_d2_counts_each_64_apart"),
    "code-summary-starts/provider-starts/8/digest": _p(
        "database/test_composed_chain.py",
        "test_a_flows_address_digest_is_nullable_and_only_a_keyed_digest_on_any_start"),
    # security-requirements.md § Required verification.
    "security-requirements/required/1": _r(ROW_SUDO),
    "security-requirements/required/2": _p(
        "operations/test_fixed_programs.py",
        "test_each_installed_program_checks_its_environment_and_word_in_its_own_process"),
    "security-requirements/required/3/scram": _p(
        "component/test_transactions_scram.py",
        "test_a_login_that_is_not_scram_is_refused_by_the_client"),
    "security-requirements/required/3/listener-and-superuser": _r(ROW_LISTENER),
    "security-requirements/required/4": _r(ROW_KEYCHAIN),
    "security-requirements/required/5": _p(
        "integration/test_log_exposure.py",
        "test_forced_failures_leave_no_test_value_in_the_realm_database_log"),
    "security-requirements/required/6": _r(ROW_PORTS),
    "security-requirements/required/7": _p(
        "operations/test_isolation_check.py",
        "test_a_removed_time_machine_exclusion_fails_isolation_backups"),
    "security-requirements/required/8": _p(
        "integration/test_log_exposure.py",
        "test_no_secret_reaches_any_log_observation_incident_or_ledger_record"),
    "security-requirements/required/9/signed-out": _p(
        "integration/test_route_inventory.py",
        "test_a_signed_out_caller_reaches_no_private_route_stream_or_asset"),
    "security-requirements/required/9/other-owner": _p(
        "integration/test_route_inventory.py",
        "test_another_owners_identifiers_behave_as_missing"),
    "security-requirements/required/10": _p(
        "operations/test_backup_agent_writing.py",
        "test_a_decided_date_below_the_minimum_or_without_its_receipt_is_refused"),
    "security-requirements/required/11": _p(
        "integration/test_import_operations.py",
        "test_a_second_pass_over_the_same_snapshot_imports_and_updates_nothing"),
    "security-requirements/required/12": _p(
        "arrangement/test_logrotate.py",
        "test_no_copy_older_than_14_days_remains_and_each_keeps_owner_and_0600"),
    "security-requirements/required/13": _p(
        "operations/test_logrotate_rules.py",
        "test_a_link_planted_under_a_logs_name_is_skipped_and_its_target_untouched"),
    # cicd-pipeline.md § 11 -- CI and the release workflow.
    "cicd-pipeline-11/ci/1": _r(ROW_FIRST_RELEASE),
    "cicd-pipeline-11/ci/2": _p(
        "operations/test_u8_tool.py",
        "test_the_verification_run_refuses_passed_with_a_phase_missing_skipped_or_failed"),
    "cicd-pipeline-11/ci/3/guard": _p(
        "operations/test_release_guard.py",
        "test_the_guard_fails_a_wrong_first_version_and_passes_the_rest"),
    "cicd-pipeline-11/ci/3/first-release": _r(ROW_FIRST_RELEASE),
    # The lead's check after build batch 9a (2026-11-11, under L1-59): the version pins and
    # the token clause each have a test of their own, and ci/5 is one entry per clause.
    "cicd-pipeline-11/ci/4": _p(
        "operations/test_u8_tool.py", "test_require_versions_refuses_a_database_off_the_pins"),
    "cicd-pipeline-11/ci/5/write-token": _p(
        "operations/test_build_workspace_gate.py",
        "test_the_complete_verification_workflow_grants_no_job_a_write_permission"),
    "cicd-pipeline-11/ci/5/budget": _p(
        "operations/test_u8_quality_floors.py", "test_a_first_load_over_its_budget_is_refused"),
    # Refusals before production changes.
    "cicd-pipeline-11/refusals/1": _p(
        "operations/test_release_install.py",
        "test_it_refuses_an_unverified_commit_a_lightweight_tag_a_tag_off_main_and_a_wrong_hash"),
    "cicd-pipeline-11/refusals/2": _p(
        "operations/test_release_install.py",
        "test_it_refuses_a_workspace_build_whose_digest_differs"),
    "cicd-pipeline-11/refusals/3": _p(
        "arrangement/test_release_environment.py", "test_a_dependency_without_a_wheel_fails"),
    "cicd-pipeline-11/refusals/4": _p(
        "operations/test_release_install.py",
        "test_the_performance_phase_is_refused_below_its_memory_or_load_threshold"),
    "cicd-pipeline-11/refusals/5": _p(
        "operations/test_release_install.py",
        "test_it_refuses_during_a_restore_a_switch_an_abort_or_a_rollback"),
    # Failures during an install.
    "cicd-pipeline-11/failures/1": _p(
        "operations/test_release_install.py",
        "test_a_failed_migration_keeps_the_earlier_owners_and_the_current_release"),
    "cicd-pipeline-11/failures/2": _p(
        "operations/test_release_install.py",
        "test_not_ready_within_ten_minutes_switches_back_and_records_the_time"),
    # Compatibility and the arrangement (L1-60, "Fix the path and hand on the rest").
    "cicd-pipeline-11/compatibility/1/planted-tag": _p(
        "operations/test_u8_tool.py",
        "test_compatibility_runs_a_planted_v2_tags_own_spec_from_its_own_worktree"),
    "cicd-pipeline-11/compatibility/1/real-release": _r(ROW_COMPATIBILITY),
    "cicd-pipeline-11/compatibility/2": _p(
        "operations/test_isolation_check.py",
        "test_an_in_progress_marker_reports_a_change_and_an_old_one_covers_nothing"),
    "cicd-pipeline-11/compatibility/3": _p(
        "operations/test_release_install.py",
        "test_the_marker_is_gone_and_the_manifest_matches_every_way_out"),
    "cicd-pipeline-11/compatibility/4": _p(
        "operations/test_installer.py",
        "test_the_in_progress_marker_covers_sixty_minutes_and_every_way_out"),
    # Release folders.
    "cicd-pipeline-11/release-folders/1": _p(
        "arrangement/test_release_environment.py",
        "test_after_a_swap_and_a_switch_back_code_loads_from_the_linked_release"),
    "cicd-pipeline-11/release-folders/2": _p(
        "operations/test_release_install.py",
        "test_step_3_refuses_a_checkout_that_does_not_measure_the_release"),
    "cicd-pipeline-11/release-folders/3": _p(
        "operations/test_release_install.py",
        "test_after_the_record_only_the_two_linked_folders_remain"),
    # After an install.
    # One bullet, two clauses, each mapped to the test that checks it.
    "cicd-pipeline-11/after-install/1/readiness": _p(
        "integration/test_start_checks.py",
        "test_readiness_evidence_records_the_running_release_tag_and_commit"),
    "cicd-pipeline-11/after-install/1/ledger": _p(
        "operations/test_release_install.py",
        "test_after_the_record_only_the_two_linked_folders_remain"),
    # BR10.3's journeys, A11Y and SEC.
    "br10-3/journeys/J01": _w("journeys.spec.ts",
                              "[J01] sign-in to library, search, paper, research, novelty and "
                              "export"),
    "br10-3/journeys/J02": _w("journeys.spec.ts",
                              "[J02] a followed topic reaches a delivered digest through the "
                              "scheduler"),
    "br10-3/journeys/J03": _w("isolation.spec.ts",
                              "[J03] memberB sees none of them in any list and reads none of "
                              "them"),
    "br10-3/journeys/J04": _w("lifecycle.spec.ts",
                              "[J04] a session revoked in another window ends its stream and "
                              "its job"),
    "br10-3/journeys/J05": _w("lifecycle.spec.ts",
                              "[J05] consent revoked while a digest, an export and a job are in "
                              "flight: none takes effect"),
    "br10-3/journeys/J06": _w("journeys.spec.ts",
                              "[J06] drafts are switched off: no save, no claim of saving, "
                              "nothing carried across a reload or an account switch"),
    "br10-3/journeys/J07": _w("journeys.spec.ts",
                              "[J07] a job is accepted, progresses, is cancelled, an unknown "
                              "outcome is reconciled, and the owner lists them"),
    "br10-3/journeys/J08": _w("lifecycle.spec.ts",
                              "[J08] withdrawal racing a digest, an export and a job; "
                              "reactivation by mail; erasure"),
    "br10-3/journeys/J09": _w("recovery.spec.ts",
                              "[J09] a backup, an erased owner, and a restore verification that "
                              "does not revive them"),
    "br10-3/journeys/J10": _w("migration.spec.ts",
                              "[J10] the dry run meets every misfit reason, changes nothing on "
                              "its second pass, and reconciles"),
    "br10-3/journeys/J11": _w("cutover.spec.ts",
                              "[J11] a switch: v1, the notice while the final run imports, then "
                              "only v2"),
    "br10-3/journeys/J12": _w("navigation.spec.ts",
                              "[J12] signed out: search is open, owner entries ask for sign-in, "
                              "operations is absent"),
    "br10-3/journeys/J13": _w("isolation.spec.ts",
                              "[J13] signed out, every private list, read, event and asset "
                              "refuses"),
    "br10-3/journeys/J14": _p("repair_exercise/test_stale_capability.py",
                              "test_stale_capability_is_never_available"),
    "br10-3/journeys/A11Y": _w("accessibility-signed-out.spec.ts",
                               "[A11Y] signed out: the entry, the legal pages and a cancelled "
                               "provider return"),
    "br10-3/journeys/SEC": _w("security.spec.ts",
                              "[SEC] a Google sign-in arrives back cross-site and signs the "
                              "linked account in"),
    # NFR8.1-NFR8.12.
    **{f"nfr8/NFR8.{number}": _r(ROW_SCALE) for number in range(1, 6)},
    "nfr8/NFR8.6/crashed-host": {"phase": "restart-host"},
    "nfr8/NFR8.6/crashed-database": {"phase": "restart-database"},
    "nfr8/NFR8.6/installation-and-rehearsal": _r(ROW_RESTART),
    "nfr8/NFR8.7/settings": _p("operations/test_templates.py",
                               "test_postgresql_conf_holds_the_required_settings"),
    "nfr8/NFR8.7/served-peak": _p(
        "operations/test_u8_phase_helpers.py",
        "test_the_performance_evidence_records_the_served_realms_peak_memory_under_the_load"),
    "nfr8/NFR8.7/production-scale": _r(ROW_MEMORY),
    "nfr8/NFR8.8/run-durations": _p(
        "component/test_misfit_decisions.py",
        "test_a_run_records_each_phases_start_and_its_duration_from_snapshot_to_report"),
    "nfr8/NFR8.8/switch-start-subject": _p(
        "operations/test_cutover_decide_words.py",
        "test_the_switch_start_subject_shows_the_accepted_dry_runs_durations_and_the_soaks_"
        "95th_percentiles"),
    "nfr8/NFR8.8/real-v1-data": _r(ROW_DRY_RUN),
    "nfr8/NFR8.9": _r(ROW_BACKUP),
    "nfr8/NFR8.10": _p("operations/test_isolation_check.py",
                       "test_a_hung_item_is_unknown_and_the_check_ends_within_its_bound"),
    "nfr8/NFR8.11/pinned-versions": _p(
        "operations/test_u8_phase_helpers.py",
        "test_the_performance_evidence_records_the_versions_it_ran_on"),
    "nfr8/NFR8.11/runtime-upgrade": _r(ROW_UPGRADE),
    "nfr8/NFR8.12/twenty-users": _r(ROW_SCALE),
    "nfr8/NFR8.12/only-migrated-accounts": _p(
        "integration/test_admission.py", "test_registration_stays_closed_until_public_activation"),
    "nfr8/NFR8.12/account-cap": _p("integration/test_admission.py",
                                   "test_the_cap_applies_once_registration_opens"),
}
