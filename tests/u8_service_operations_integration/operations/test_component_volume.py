"""Every U8 test file is mapped, each component has at least five tests, and each key
boundary names a test its phase runs (U8 plan Step 98(c), written and registered in Step
98(f)).

`COMPONENTS` links the 18 components of the instructions' test-volume line to their files,
and `GROUPS` links the named groups: the assembly and routes, the earlier units' guards,
the environment tool and the repair exercise. The files come from the `database`,
`repository`, `component`, `integration`, `operations`, `arrangement` and `repair_exercise`
folders, and every `test_*.py` there is mapped. Tests are counted by AST: each top-level
`test_` function counts once, a parametrized one included, and a file mapped under two
components counts for each. A component above 8 tests carries its reason and is kept, as
U5's and U6's were (test-results.md:154, 255).

Only the top folder has `__init__.py` and `conftest.py`, so a test file's basename must be
unique across the seven folders (`unit-test-instructions.md:25`, replaced by its loop-back
2 section, L2-11): a shared basename stops the whole-folder collection at its import.
`duplicate_basenames` finds one.

`BOUNDARIES` names, for each of the 14 rows of logical-components.md § 2 (the table's text
pinned by SHA-256), a pytest node in a file its phase collects, or, for the two rows real
only at the installation, a row of the plan's "Completion and evidence boundaries".
Functions are found by AST through `lane_map.py`. The table helpers come from
`test_required_items.py`, as `test_no_real_secrets.py` imports `test_never_mocked.py`'s;
`lane_map.py` itself imports no test module.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

from tests.u8_service_operations_integration import lane_map
from tests.u8_service_operations_integration import required_items as ri
from tests.u8_service_operations_integration.operations import test_required_items as req

ROOT = Path(__file__).resolve().parents[3]
T = ri.T
FOLDERS = ("database", "repository", "component", "integration", "operations",
           "arrangement", "repair_exercise")
MINIMUM, USUAL_MAXIMUM = 5, 8
LOGICAL = f"{ri.RECORD}/nfr-design/logical-components.md"
LOGICAL_HEADING = "## 2. How the components connect"
LOGICAL_SHA256 = "1d628b961e4be528b4504d6387b7737bd14f641a272e7b32a7bcb4ca123ac823"


def _files(*paths: str) -> tuple[str, ...]:
    return tuple(f"{T}/{path}" for path in paths)


# The 18 components (unit-test-instructions.md, "Test volume"), each with its files and,
# above 8 tests, the reason it is kept.
COMPONENTS: dict[str, dict] = {
    "the ledger": {"files": _files(
        "repository/test_ledger_store.py", "component/test_ledger_component.py",
        "component/test_ledger_damage.py", "operations/test_ledger_cli.py"),
        "reason": "the ledger is every effect's record: its store, its damage rules and "
                  "its command each need their own cases"},
    "observations and readiness": {"files": _files(
        "repository/test_observation_store.py", "component/test_observations.py",
        "component/test_readiness.py", "component/test_producers.py",
        "component/test_latency_summaries.py", "component/test_model_evidence.py",
        "component/test_earlier_profile_health.py", "component/test_request_context.py",
        "integration/test_health_api.py"),
        "reason": "every capability has its own producer, and readiness is read by every "
                  "screen"},
    "incidents": {"files": _files("component/test_incidents.py"),
                  "reason": "each capability's opening, tolerance and closing rule"},
    "the lifecycle participants": {"files": _files(
        "component/test_tombstones.py", "component/test_retained_copies.py",
        "component/test_retention_date.py", "component/test_research_participant.py",
        "integration/test_lifecycle_manifest.py", "integration/test_tombstone_replay.py",
        "integration/test_reactivation.py", "integration/test_waiting_parts.py"),
        "reason": "each owner's participant is checked against withdrawal, erasure and "
                  "reactivation"},
    "AccountAccess's policy and limits": {"files": _files(
        "component/test_production_policy.py", "component/test_password_checks.py",
        "component/test_sign_in_failures.py", "component/test_transactions_scram.py",
        "component/test_account_mail.py", "component/test_allowance.py",
        "repository/test_entry_limits.py", "integration/test_sign_in_limits.py",
        "integration/test_admission.py", "integration/test_account_routes.py",
        "integration/test_account_mail_routes.py", "integration/test_first_sign_in.py"),
        "reason": "D1, D2, D12 and the provider starts each list required items of their "
                  "own"},
    "the providers": {"files": _files(
        "component/test_identity_providers.py", "component/test_provider_activation.py",
        "component/test_outward_wiring.py", "integration/test_first_effects.py"),
        "reason": "four providers, each with its gate, its activation and its first "
                  "effect"},
    "search": {"files": _files(
        "component/test_complete_search.py", "component/test_corpus_limits.py",
        "repository/test_search_candidates.py", "integration/test_signed_in_search.py"),
        "reason": "the corpus limits, the embedding bound and the candidates' query each "
                  "need their cases"},
    "the backup agent": {"files": _files(
        "repository/test_catalogue.py", "component/test_backups_evidence.py",
        "operations/test_backup_agent_commands.py",
        "operations/test_backup_agent_disposal.py", "operations/test_backup_agent_status.py",
        "operations/test_backup_agent_writing.py", "operations/test_snapshot_archives.py",
        "integration/test_backup_agent_in_the_realm.py",
        "integration/test_backup_agent_restore.py"),
        "reason": "each of the agent's commands refuses on its own, as BR4 lists"},
    "PlatformControl's operations": {"files": _files(
        "operations/test_u8_protocols.py", "operations/test_drivers.py",
        "operations/test_service_words.py", "operations/test_inventory_words.py",
        "operations/test_reconcile_unknown.py", "operations/test_decisions.py"),
        "reason": "every bound protocol, its drivers and its words leave a receipt each"},
    "recovery": {"files": _files(
        "component/test_recovery_effects.py", "component/test_recovery_requests.py",
        "operations/test_recovery_words.py", "integration/test_restore_verification.py",
        "integration/test_production_restore.py"),
        "reason": "restore verification and the production restore each run their own "
                  "path"},
    "migration": {"files": _files(
        "repository/test_owner_imports.py", "component/test_misfit_decisions.py",
        "integration/test_import_operations.py", "integration/test_imported_usage.py",
        "integration/test_migration_run.py", "integration/test_production_import_runner.py",
        "integration/test_production_migration_platform.py",
        "operations/test_migration_words.py", "operations/test_production_migration_words.py",
        "operations/test_v1_environment.py"),
        "reason": "every owner's import, each misfit reason and the run's words"},
    "cutover": {"files": _files(
        "component/test_cutover_machine.py", "component/test_cutover_words.py",
        "component/test_disposal_pass.py", "component/test_soak_and_rehearsal.py",
        "component/test_volume_retirement.py", "integration/test_cutover_journeys.py",
        "operations/test_cutover_decide_words.py",
        "operations/test_production_cutover_wiring.py"),
        "reason": "the cutover's states, its words and its rollback each need their own "
                  "cases"},
    "the standing job": {"files": _files(
        "operations/test_standing_lanes.py", "operations/test_availability.py"),
        "reason": "every lane, its schedule and its pings"},
    "the isolation check": {"files": _files(
        "operations/test_isolation_check.py", "operations/test_exclusion_both_ways.py",
        "operations/test_allowlist_sites.py", "arrangement/test_macos_adapters_live.py"),
        "reason": "each isolation item has its own check and its own unknown"},
    "rotation": {"files": _files(
        "operations/test_logrotate_rules.py", "arrangement/test_logrotate.py"),
        "reason": "D11's seven items and the root run each need their cases"},
    "the maintenance server": {"files": _files("component/test_maintenance_server.py"),
                               "reason": "each notice page and its headers"},
    "the installer": {"files": _files(
        "operations/test_installer.py", "operations/test_templates.py",
        "operations/test_fixed_programs.py", "operations/test_credential_release.py",
        "operations/test_root_jobs.py", "operations/test_production_tool.py",
        "operations/test_peer_map_proof.py", "operations/test_role_page_reads.py",
        "arrangement/test_template_lint.py"),
        "reason": "every installed file, program, job and grant is checked"},
    "the release command": {"files": _files(
        "operations/test_release_install.py", "operations/test_release_guard.py",
        "arrangement/test_release_environment.py"),
        "reason": "each of the install's steps refuses, fails and switches back on its own"},
}

# The named groups, beside the components.
GROUPS: dict[str, tuple[str, ...]] = {
    "the assembly and routes": _files(
        "database/test_assistance_job_times.py", "database/test_composed_chain.py",
        "database/test_database_locale.py", "database/test_research_retention.py",
        "database/test_research_waits.py", "database/test_u8_schema.py",
        "repository/test_largest_admitted_write.py", "repository/test_owner_jobs.py",
        "component/test_capacity.py", "component/test_log_events.py",
        "component/test_production_profile.py", "component/test_registry.py",
        "component/test_research_execution.py", "component/test_research_model.py",
        "integration/test_accepting_work.py", "integration/test_body_limit.py",
        "integration/test_boundary.py", "integration/test_complete_assistance.py",
        "integration/test_complete_controls.py", "integration/test_complete_library.py",
        "integration/test_complete_usage.py", "integration/test_host_routes.py",
        "integration/test_jobs_api.py", "integration/test_large_paper_assistance.py",
        "integration/test_log_exposure.py", "integration/test_model_lane.py",
        "integration/test_navigation_api.py", "integration/test_operations_api.py",
        "integration/test_paper_assets.py", "integration/test_personal_settings.py",
        "integration/test_production_composition.py", "integration/test_rehearsal_bound.py",
        "integration/test_route_inventory.py", "integration/test_start_checks.py",
        "integration/test_static_routes.py", "integration/test_worker_isolation.py",
        "operations/test_assemblies_alone.py", "operations/test_import_boundaries.py",
        "operations/test_production_wiring.py"),
    "the earlier units' guards": _files(
        "component/test_consumer_inventory.py", "component/test_job_hook_defaults.py",
        "component/test_u2_seam_defaults.py", "component/test_u5_seam_defaults.py",
        "component/test_u7_seam_defaults.py", "integration/test_u2_fail_closed.py",
        "integration/test_u5_seams.py", "operations/test_built_file_pins.py",
        "operations/test_u2_ci_coverage.py", "operations/test_u2_restore_image.py",
        "operations/test_u2_scope.py", "operations/test_u3_scope.py",
        "operations/test_u4_scope.py", "operations/test_u5_scope.py",
        "operations/test_u6_scope.py", "operations/test_u7_fail_closed.py",
        "operations/test_u7_scope.py"),
    "the environment tool": _files(
        "operations/test_u8_tool.py", "operations/test_u8_phase_helpers.py",
        "operations/test_u8_quality_floors.py", "operations/test_u8_coverage_reports.py",
        "operations/test_build_workspace_gate.py", "operations/test_lint_gate.py",
        "operations/test_fixture_clock.py", "operations/test_realm_checks.py",
        "operations/test_never_mocked.py", "operations/test_no_real_secrets.py",
        "operations/test_required_items.py", "operations/test_component_volume.py",
        "operations/test_macos_report_scope.py", "operations/test_scram_sites.py"),
    "the repair exercise": _files("repair_exercise/test_stale_capability.py"),
}

# Each row of logical-components.md § 2, by its From and To cells, with the test or the
# boundaries row that checks it.
ROW_UNLOCK = ("NFR3.7 and NFR7.3: the Time Machine exclusions; after an authorized restart, "
              "every job runs and the volume is unlocked before anyone logs in, ready within "
              "3 minutes")
STANDING = "operations/test_standing_lanes.py"
BOUNDARIES: dict[tuple[str, str], dict] = {
    ("A browser", "v2's host, through Cloudflare and the tunnel"): {"pytest": (
        "integration/test_boundary.py",
        "test_a_request_through_the_standin_reaches_its_browser_route_as_https")},
    ("The host and the workers", "v2's PostgreSQL"): {"pytest": (
        "component/test_transactions_scram.py",
        "test_a_login_that_is_not_scram_is_refused_by_the_client")},
    ("The host and the workers", "the model runtime"): {"pytest": (
        "component/test_model_evidence.py",
        "test_search_past_the_embedding_bound_answers_by_words_with_its_limitation")},
    ("The workers", "Google, ORCID, Resend, Notion"): {"pytest": (
        "component/test_provider_activation.py",
        "test_an_active_provider_degrades_and_serves_again")},
    ("The standing job", "the backup agent"): {"pytest": (
        STANDING, "test_the_backup_lane_runs_at_0400_seoul_on_the_current_database")},
    ("The standing job", "the isolation check"): {"pytest": (
        STANDING, "test_the_isolation_lane_runs_platformcontrols_bound_check")},
    # Step 67's failed-ledger test.
    ("The standing job", "the ledger component"): {"pytest": (
        STANDING, "test_a_failed_ledger_call_makes_the_backup_and_verification_pings_report_"
                  "fail")},
    ("The standing job", "the public address and the local health route"): {"pytest": (
        "operations/test_availability.py", "test_a_missing_slot_counts_as_down")},
    ("The standing job", "healthchecks.io"): {"pytest": (
        "operations/test_availability.py",
        "test_a_down_slot_pings_fail_and_the_next_up_slot_clears_it")},
    ("You, through the operator tool", "the fixed commands"): {"row": ri.ROW_IN_PERSON},
    ("The backup agent", "the backup volume"): {"pytest": (
        "operations/test_backup_agent_status.py",
        "test_a_mismatched_volume_identity_and_an_unencrypted_volume_fail_closed")},
    ("The backup agent", "v2's instance, and v1's data plane for snapshots"): {"pytest": (
        "integration/test_backup_agent_in_the_realm.py",
        "test_the_realm_driver_runs_the_same_agent_against_the_standin_volume")},
    ("The unlock job", "the System keychain, then `diskutil`"): {"row": ROW_UNLOCK},
    ("ServiceOperations", "PlatformControl's evidence"): {"pytest": (
        "component/test_producers.py",
        "test_platform_status_carries_the_agents_status_and_failed_writes")},
}


# --- the volume check --------------------------------------------------------------------


def count_tests(source: str) -> int:
    """The top-level `test_` functions of a module, each once."""
    tree = ast.parse(source)
    return sum(1 for node in tree.body
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
               and node.name.startswith("test_"))


def present_files(root: Path = ROOT) -> dict[str, str]:
    """Every `test_*.py` of the seven folders, with its text."""
    return {f"{T}/{folder}/{path.name}": path.read_text(encoding="utf-8")
            for folder in FOLDERS for path in sorted((root / T / folder).glob("test_*.py"))}


def volume_problems(files: dict[str, str], components: dict[str, dict],
                    groups: dict[str, tuple[str, ...]]) -> tuple[list[str], dict[str, int]]:
    """The problems found, and each component's count."""
    problems = []
    mapped = {file for entry in components.values() for file in entry["files"]}
    mapped |= {file for names in groups.values() for file in names}
    for file in sorted(set(files) - mapped):
        problems.append(f"{file}: mapped to nothing")
    for file in sorted(mapped - set(files)):
        problems.append(f"{file}: mapped, but no such test file")
    counts = {}
    for name, entry in components.items():
        counts[name] = sum(count_tests(files[file]) for file in entry["files"] if file in files)
        if counts[name] < MINIMUM:
            problems.append(f"{name}: {counts[name]} tests, fewer than {MINIMUM}")
        if counts[name] > USUAL_MAXIMUM and not str(entry.get("reason", "")).strip():
            problems.append(f"{name}: {counts[name]} tests and no reason above "
                            f"{USUAL_MAXIMUM}")
    return problems, counts


# --- the boundary check ------------------------------------------------------------------


def logical_rows(text: str) -> list[tuple[str, str]]:
    table = req.table_block(text, LOGICAL_HEADING)
    return [tuple(cell.strip() for cell in row.strip().strip("|").split("|")[:2])
            for row in table.splitlines()[2:]]


def boundary_problems(text: str, boundaries: dict, runner, phases,
                      cells: list[str]) -> list[str]:
    problems = []
    table = req.table_block(text, LOGICAL_HEADING)
    if hashlib.sha256(table.encode("utf-8")).hexdigest() != LOGICAL_SHA256:
        problems.append("logical-components § 2: the table differs from its pin")
    rows = logical_rows(text)
    for row in rows:
        target = boundaries.get(row)
        if target is None:
            problems.append(f"{row[0]} → {row[1]}: names no test")
        elif "row" in target:
            if target["row"] not in cells:
                problems.append(f"{row[0]} → {row[1]}: names no boundaries row")
        elif not lane_map.pytest_phases(f"{T}/{target['pytest'][0]}::{target['pytest'][1]}",
                                        runner=runner, phases=phases):
            problems.append(f"{row[0]} → {row[1]}: its test is in no file a phase runs")
    for row in sorted(set(boundaries) - set(rows)):
        problems.append(f"{row[0]} → {row[1]}: not a row of the table")
    return problems


@pytest.fixture(scope="module")
def tree():
    runner, phases = lane_map.modules()
    plan = (ROOT / req.PLAN).read_text(encoding="utf-8")
    return {
        "files": present_files(),
        "logical": (ROOT / LOGICAL).read_text(encoding="utf-8"),
        "cells": req.first_cells(req.table_block(plan, req.BOUNDARIES)),
        "runner": runner, "phases": phases,
    }


# --- the tests ---------------------------------------------------------------------------


def test_every_u8_test_file_is_mapped_and_each_component_has_at_least_five_tests(tree):
    problems, counts = volume_problems(tree["files"], COMPONENTS, GROUPS)
    assert problems == [], "\n".join(problems)
    assert len(COMPONENTS) == 18
    assert list(GROUPS) == ["the assembly and routes", "the earlier units' guards",
                            "the environment tool", "the repair exercise"]
    # Every file present is mapped, and this module among them.
    assert f"{T}/operations/{Path(__file__).name}" in tree["files"]
    assert all(count >= MINIMUM for count in counts.values()), counts


def test_each_key_boundary_names_a_test_its_phase_runs(tree):
    problems = boundary_problems(tree["logical"], BOUNDARIES, tree["runner"],
                                 tree["phases"], tree["cells"])
    assert problems == [], "\n".join(problems)
    assert len(logical_rows(tree["logical"])) == 14
    assert BOUNDARIES[("The standing job", "the ledger component")]["pytest"][0] == STANDING
    # The two rows real only at the installation rest on boundaries rows.
    assert [row for row, target in BOUNDARIES.items() if "row" in target] == [
        ("You, through the operator tool", "the fixed commands"),
        ("The unlock job", "the System keychain, then `diskutil`")]


def test_a_component_below_five_an_unmapped_file_or_an_unnamed_boundary_fails(tree):
    files = tree["files"]
    # A component whose files hold 4 tests.
    four = dict(files)
    four[f"{T}/component/test_maintenance_server.py"] = "".join(
        f"def test_{index}():\n    pass\n" for index in range(4))
    problems, _ = volume_problems(four, COMPONENTS, GROUPS)
    assert any("the maintenance server: 4 tests" in problem for problem in problems), problems
    # A test file mapped to nothing.
    extra = {**files, f"{T}/operations/test_planted_unmapped.py": "def test_x():\n    pass\n"}
    problems, _ = volume_problems(extra, COMPONENTS, GROUPS)
    assert problems == [f"{T}/operations/test_planted_unmapped.py: mapped to nothing"]
    # A boundary whose test was renamed.
    renamed = {**BOUNDARIES, ("The standing job", "the ledger component"): {"pytest": (
        STANDING, "test_a_failed_ledger_call_makes_the_pings_report_fail")}}
    problems = boundary_problems(tree["logical"], renamed, tree["runner"], tree["phases"],
                                 tree["cells"])
    assert problems == ["The standing job → the ledger component: its test is in no file a "
                        "phase runs"]
    # A component above 8 with no reason fails too.
    bare = {**COMPONENTS, "the installer": {"files": COMPONENTS["the installer"]["files"]}}
    problems, _ = volume_problems(files, bare, GROUPS)
    assert any(problem.startswith("the installer:") for problem in problems), problems


# --- Unique basenames (Step 141(a); L2-11) ---------------------------------------------------


def duplicate_basenames(files: dict[str, str]) -> list[str]:
    """The sorted basenames more than one of `present_files`' keys share."""
    seen: dict[str, int] = {}
    for file in files:
        name = file.rsplit("/", 1)[-1]
        seen[name] = seen.get(name, 0) + 1
    return sorted(name for name, count in seen.items() if count > 1)


def test_every_test_file_basename_is_unique_across_the_layer_folders(tree):
    assert duplicate_basenames(tree["files"]) == []
    planted = {**tree["files"], f"{T}/database/test_u5_seam_defaults.py": ""}
    assert duplicate_basenames(planted) == ["test_u5_seam_defaults.py"]
