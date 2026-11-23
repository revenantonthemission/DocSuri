"""U6:code-generation-plan:testing-contract-test-volume; L1-8: the component -> test-file
map, and the five-definition floor, as files rather than a claim.

`COMPONENT_FILES` covers the python-test components of logical-components §1 plus the
`EnvironmentTool` group; `EXTERNAL_FILES` carries `SharedContractAmendments` (its cases
run in the shared contract suite); `FRONTEND_FILES` decomposes `ExportUI` per
`src/u6-export` module, counted from `it(`/`test(` lines because no python ast exists
for TSX. The four Playwright specs are journeys and carry no per-component floor.
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
U6 = ROOT / "tests/u6_approved_export"

COMPONENT_FILES = {
    "ExportRoutes": [
        "integration/test_export_http.py",
        "integration/test_export_body_bounds.py",
        "integration/test_pending_connect.py",
        "integration/test_account_purpose.py",
        "integration/test_interactive_admission.py",
    ],
    "ExportService": [
        "component/test_service_connection.py",
        "component/test_service_destinations.py",
        "component/test_service_preview.py",
        "component/test_service_approval.py",
        "component/test_service_outcomes.py",
        "component/test_binding_check.py",
        "component/test_export_lifecycle.py",
    ],
    "RenderPolicy": ["component/test_rendering.py"],
    "ExportStore": [
        "database/test_export_schema.py",
        "database/test_export_functions.py",
        "database/test_export_grants.py",
        "database/test_pace_at_fake.py",
        "repository/test_approval_effect_store.py",
        "repository/test_connection_store.py",
        "repository/test_housekeeping_store.py",
        "repository/test_lane_store.py",
        "repository/test_owner_guard.py",
        "repository/test_pace_store.py",
        "repository/test_preview_store.py",
        "repository/test_replay_records.py",
        "repository/test_status_counts.py",
        "repository/test_unknown_check_cadence.py",
    ],
    "TokenVault": [
        "operations/test_token_vault.py",
        "component/test_token_exposure.py",
    ],
    "TokenKeyring": ["operations/test_token_keyring.py"],
    "KeyCustody": [
        "operations/test_key_custody.py",
        "operations/test_control_keys_parity.py",
        "operations/test_key_never_elsewhere.py",
    ],
    "NotionAdapter": [
        "component/test_notion_adapter.py",
        "component/test_classification.py",
        "component/test_provider_text.py",
    ],
    "NotionSession": [
        "component/test_notion_session.py",
        "component/test_log_content.py",
        "component/test_plaintext_lifetime.py",
    ],
    "GuardedTransport": ["component/test_guarded_transport.py"],
    "InteractiveGate": [
        "component/test_interactive_gate.py",
        "integration/test_interactive_admission.py",
    ],
    "FakeNotion": ["component/test_fake_notion.py"],
    "ExportWorker": [
        "component/test_worker_pass.py",
        "component/test_check_schedule.py",
        "integration/test_session_housekeeping.py",
    ],
    "ExportLane": [
        "component/test_lane_write_path.py",
        "component/test_reconciliation.py",
        "integration/test_lane_transactions.py",
        "integration/test_lifecycle_in_flight.py",
    ],
    "ExportLifecycleParticipant": [
        "component/test_export_lifecycle.py",
        "integration/test_lifecycle_projection.py",
        "integration/test_lifecycle_in_flight.py",
    ],
    "KeyCommands": ["operations/test_key_commands.py"],
    "ExportComposition": [
        "component/test_export_composition.py",
        "component/test_real_export_composition.py",
        "component/test_free_terms_evidence.py",
        "component/test_real_export_gates.py",
        "component/test_export_policy.py",
        "component/test_u3_export_gate.py",
        "integration/test_export_assembly.py",
        "integration/test_real_research_rig.py",
    ],
    "AccountAccessA8": [
        "integration/test_lifecycle_projection.py",
        "integration/test_account_purpose.py",
        "repository/test_owner_guard.py",
    ],
    "EnvironmentTool": [
        "operations/test_u6_runner.py",
        "operations/test_u6_serve.py",
        "operations/test_u6_preservation.py",
        "operations/test_u6_profile_binding.py",
        "operations/test_u6_browser_fixtures.py",
        "operations/test_u6_real_export_checks.py",
        "operations/test_coverage_contract.py",
        "operations/test_u6_test_volume.py",
        "operations/test_u6_lint_gate.py",
    ],
}

EXTERNAL_FILES = {"SharedContractAmendments": ["shared/python/tests/test_export_contract.py"]}

FRONTEND_FILES = {
    "src/u6-export/api.ts": ["frontend/test/u6-export/api.test.ts"],
    "src/u6-export/connect-form.tsx": ["frontend/test/u6-export/connect-form.test.tsx"],
    "src/u6-export/destination-step.tsx": ["frontend/test/u6-export/destination-step.test.tsx"],
    "src/u6-export/dialogs.tsx": ["frontend/test/u6-export/dialogs.test.tsx"],
    "src/u6-export/export-flow.tsx": [
        "frontend/test/u6-export/export-flow.test.tsx",
        "frontend/test/u6-export/approve-export.test.tsx",
    ],
    "src/u6-export/export-view.tsx": ["frontend/test/u6-export/export-view.test.tsx"],
    "src/u6-export/history.tsx": ["frontend/test/u6-export/history.test.tsx"],
    "src/u6-export/outcome-step.tsx": ["frontend/test/u6-export/outcome-step.test.tsx"],
    "src/u6-export/preview-step.tsx": ["frontend/test/u6-export/preview-step.test.tsx"],
    "src/u6-export/status.tsx": ["frontend/test/u6-export/status-accessibility.test.tsx"],
}

KEY_BOUNDARIES = (
    "operations/test_token_keyring.py",
    "operations/test_token_vault.py",
    "operations/test_key_custody.py",
    "operations/test_key_commands.py",
    "operations/test_control_keys_parity.py",
    "operations/test_key_never_elsewhere.py",
)

FURTHER_INTEGRATION = (
    "integration/test_pending_connect.py",
    "integration/test_lifecycle_projection.py",
)

PLAYWRIGHT_SPECS = (
    "frontend/e2e/u6-approved-export/journeys.spec.ts",
    "frontend/e2e/u6-approved-export/keyboard.spec.ts",
    "frontend/e2e/u6-approved-export/accessibility.spec.ts",
    "frontend/e2e/u6-approved-export/reflow.spec.ts",
)

CASE_LINE = re.compile(r"^\s*(?:it|test)(?:\.\w+)*\s*\(", re.MULTILINE)


def definitions(path: Path) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    )


def cases(path: Path) -> int:
    return len(CASE_LINE.findall(path.read_text(encoding="utf-8")))


def test_every_test_file_is_mapped():
    walked = {path.relative_to(U6).as_posix() for path in U6.rglob("test_*.py")}
    mapped = {path for files in COMPONENT_FILES.values() for path in files}

    assert walked - mapped == set()
    for path in mapped:
        assert (U6 / path).is_file(), path
    for path in EXTERNAL_FILES["SharedContractAmendments"]:
        assert (ROOT / path).is_file(), path
    declared = {Path(path).name for path in EXTERNAL_FILES["SharedContractAmendments"]}
    shared = {path.name for path in (ROOT / "shared/python/tests").glob("test_*export*.py")}
    assert shared == declared


def test_components_carry_at_least_five_tests():
    counts = {
        name: sum(definitions(U6 / path) for path in files)
        for name, files in COMPONENT_FILES.items()
    }
    for name, files in EXTERNAL_FILES.items():
        counts[name] = sum(definitions(ROOT / path) for path in files)

    assert "InteractiveGate" in COMPONENT_FILES
    assert "ExportWorker" in COMPONENT_FILES
    assert counts["InteractiveGate"] >= 5
    assert counts["ExportWorker"] >= 5
    assert {name: count for name, count in counts.items() if count < 5} == {}


def test_named_key_boundaries_and_further_integration_files_exist():
    assert len(KEY_BOUNDARIES) == 6
    assert len(FURTHER_INTEGRATION) == 2
    mapped = {path for files in COMPONENT_FILES.values() for path in files}

    for path in (*KEY_BOUNDARIES, *FURTHER_INTEGRATION):
        assert path in mapped, path
        assert definitions(U6 / path) >= 1, path


def test_frontend_volume_and_the_playwright_specs():
    modules = {path.name for path in (ROOT / "frontend/src/u6-export").iterdir()}
    assert {Path(key).name for key in FRONTEND_FILES} == modules - {"copy.ts", "export.css"}
    for key in FRONTEND_FILES:
        assert (ROOT / "frontend" / key).is_file(), key

    walked = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "frontend/test/u6-export").glob("*.test.ts*")
    }
    mapped = {path for files in FRONTEND_FILES.values() for path in files}
    assert walked - mapped == set()

    for module, files in FRONTEND_FILES.items():
        total = 0
        for path in files:
            assert (ROOT / path).is_file(), path
            total += cases(ROOT / path)
        assert total >= 5, (module, total)

    for spec in PLAYWRIGHT_SPECS:
        assert (ROOT / spec).is_file(), spec
        assert cases(ROOT / spec) >= 1, spec
