# Cross-unit traceability

Checked on 2026-11-23, in the stage's sixth run, by `aidlc engine sensor-traceability --stage build-and-test`, which reads the three per-unit traceability files:

- `construction/u5-topics-digests/code-generation/traceability.json`
- `construction/u6-approved-export/code-generation/traceability.json`
- `construction/u8-service-operations-integration/code-generation/traceability.json`

It traced 209 IDs: the functional requirements FR1.1–FR4.2 of `inception/requirements-analysis/requirements.md` and the NFR and BR identifiers the three Units' designs carry. User Stories did not run in this workflow, so there are no acceptance criteria to enumerate. An ID counts as covered when at least one Unit records it as built and names the files that build it. Entries a Unit marks `N/A` because the unit story map assigns the ID to another Unit neither cover nor block.

## Verdict

**FAIL: 190 of 209 IDs covered.** The sensor printed `"pass":false` and these 19 under `uncovered`: FR4.1, FR4.2, NFR1.6, NFR3.11, NFR7.2, NFR7.3, NFR8.1, NFR8.2, NFR8.3, NFR8.4, NFR8.5, NFR8.6, NFR9.8, BR6.11, BR6.12, BR7.3, BR7.8, BR10.4 and BR10.5. The 19 uncovered IDs are all U8's, and U8 records each as `Deferred`: it built and tested the code. The evidence each ID asks for comes from CI (the macOS job, and the first GitHub runs of U8's workflows, including the complete verification lane that BR10.4 waits for), the installation, each install's performance phase and the soak, the dry runs on real v1 data, the switch with its maintainer-only and rollback windows, v1's restart rehearsal, or the first release. For FR4.2, U8 also names Build and Test, this stage, which is still in progress. Apart from Build and Test, these are later stages in this plan, none of them started. Each uncovered ID is a Build and Test finding for the approval gate.

The first run's check (2026-10-27) read the 25 requirements of `requirements.md` (FR1–FR4 with their sub-requirements, and NFR1–NFR6) and found FR4, FR4.1 and FR4.2 uncovered. This run traces 209 of the 219 identifiers the three traceability files carry: all but the ten top-level IDs FR1–FR4 and NFR1–NFR6, which get no row of their own. FR4, which U8 marks `Deferred`, is therefore no longer reported, though it is not covered. FR4.1 and FR4.2 stay uncovered for the same reason as before; the other 17 are U8's own NFR and BR identifiers with the same kind of deferral. The fifth run's check, on 2026-11-19, gave the same result as the fourth run's on 2026-11-17 and the third run's on 2026-11-15, ID for ID and file for file. The sixth run's check, on 2026-11-23, after loop-back 4 reopened U5 and U8 and rewrote their traceability files (U6's was not reopened), gives the same 209 IDs and the same 19 uncovered. One row changed: BR1.2 now also names U5's `backend/modules/topics/u5_scheduled_instant.sql`, the migration loop-back 4 added to U5. Every other row names the same Units and files as the fifth run's.

## Per ID

| ID | Covered | Units | Target files |
|---|---|---|---|
| FR1.1 | Yes | U5 | `backend/modules/topics/service.py` |
| FR1.2 | Yes | U5 | `backend/modules/topics/repository.py` |
| FR1.3 | Yes | U5 | `backend/modules/topics/repository.py` |
| FR1.4 | Yes | U5 | `backend/modules/accounts/integrations/digest_email.py`, `backend/u5_real_delivery.py`, `backend/modules/topics/u5_refusal_detail.sql`, `backend/modules/topics/u5_real_send_retention.sql`, `scripts/u5_real_delivery.py` |
| FR1.5 | Yes | U5 | `backend/modules/topics/unsubscribe.py`, `backend/modules/topics/service.py` |
| FR1.6 | Yes | U5 | `backend/modules/topics/control_lifecycle.py` |
| FR2.1 | Yes | U6 | `backend/modules/export/token_vault.py` |
| FR2.2 | Yes | U6 | `backend/modules/export/rendering.py` |
| FR2.3 | Yes | U6 | `backend/modules/export/approval_store.py` |
| FR2.4 | Yes | U6 | `backend/modules/export/lane.py` |
| FR2.5 | Yes | U6 | `backend/modules/export/binding.py` |
| FR3.1 | Yes | U8 | `backend/u8_registry.py` |
| FR3.2 | Yes | U8 | `scripts/verify_docsuri_u8.py` |
| FR4.1 | **No** (`Deferred`) | U8 | none built in full: see below |
| FR4.2 | **No** (`Deferred`) | U8 | none built in full: see below |
| NFR1.1 | Yes | U5, U6, U8 | `backend/modules/topics/repository.py`, `backend/modules/export/repository.py`, `backend/production_boundary.py` |
| NFR1.2 | Yes | U5, U6, U8 | `backend/modules/topics/repository.py`, `backend/modules/export/worker.py`, `backend/modules/operations/http.py` |
| NFR2.1 | Yes | U5, U8 | `backend/modules/topics/delivery.py`, `backend/modules/accounts/services/first_sign_in.py` |
| NFR2.2 | Yes | U5, U8 | `backend/modules/topics/errors.py`, `backend/modules/accounts/integrations/provider_gate.py` |
| NFR4.1 | Yes | U5, U6, U8 | `backend/modules/topics/u5_run_guard.sql`, `backend/modules/export/approval_store.py`, `backend/modules/operations/recovery.py` |
| NFR4.2 | Yes | U5, U6, U8 | `backend/modules/topics/u5_schema.sql`, `backend/modules/export/rendering.py`, `ops/src/docsuri_ops/u8_platform/u8_protocols.py` |
| NFR4.3 | Yes | U5, U6, U8 | `backend/u5_policy.py`, `backend/modules/export/lane.py`, `backend/modules/operations/ledger.py` |
| NFR5.1 | Yes | U5, U6, U8 | `frontend/src/u5-topics/topics-view.tsx`, `frontend/src/u5-topics/topics.css`, `frontend/e2e/u5-topics-digests/settings-accessibility.spec.ts`, `frontend/e2e/u6-approved-export/accessibility.spec.ts`, `frontend/e2e/u8-complete/accessibility.spec.ts` |
| NFR6.1 | Yes | U5, U6, U8 | `backend/u5_policy.py`, `backend/u5_real_delivery.py`, `backend/pyproject.toml`, `backend/pyproject.toml` |
| BR1.1 | Yes | U5, U6, U8 | `backend/modules/topics/service.py`, `backend/modules/export/token_vault.py`, `backend/u8_registry.py` |
| BR1.2 | Yes | U5, U6, U8 | `backend/modules/topics/scheduler.py`, `backend/modules/topics/u5_scheduled_instant.sql`, `backend/modules/export/service.py`, `backend/u8_host.py` |
| BR1.3 | Yes | U5, U6, U8 | `backend/modules/topics/repository.py`, `backend/modules/export/connection_store.py`, `backend/modules/operations/readiness.py` |
| BR1.4 | Yes | U5, U6, U8 | `backend/modules/topics/delivery.py`, `backend/u5_real_delivery.py`, `backend/modules/topics/scheduler.py`, `backend/modules/export/connection_store.py`, `backend/u8_migrations.py` |
| BR2.1 | Yes | U5, U6, U8 | `backend/modules/topics/preparation.py`, `backend/modules/export/service.py`, `backend/modules/accounts/u8_lifecycle.py` |
| BR2.2 | Yes | U5, U6, U8 | `backend/modules/topics/repository.py`, `backend/modules/export/service.py`, `backend/u8_workers.py` |
| BR2.3 | Yes | U5, U6, U8 | `backend/modules/topics/preparation.py`, `backend/modules/export/preview_store.py`, `backend/modules/research/control_lifecycle.py` |
| BR2.4 | Yes | U5, U6, U8 | `backend/modules/topics/u5_run_guard.sql`, `backend/modules/export/rendering.py`, `backend/u8_workers.py` |
| BR3.1 | Yes | U5, U6, U8 | `backend/modules/topics/u5_schema.sql`, `backend/modules/export/approval_store.py`, `backend/modules/operations/readiness.py` |
| BR3.2 | Yes | U5, U6, U8 | `backend/modules/topics/delivery.py`, `backend/modules/export/approval_store.py`, `backend/modules/operations/observations.py` |
| BR3.3 | Yes | U5, U6, U8 | `backend/modules/topics/scheduler.py`, `backend/modules/export/lane.py`, `backend/modules/operations/producers.py` |
| BR3.4 | Yes | U5, U6, U8 | `backend/modules/topics/scheduler.py`, `backend/modules/export/worker.py`, `backend/modules/operations/observations.py` |
| BR4.1 | Yes | U5, U6, U8 | `backend/modules/topics/service.py`, `backend/modules/topics/unsubscribe.py`, `backend/modules/export/rendering.py`, `backend/modules/operations/recovery_procedures.py` |
| BR4.2 | Yes | U5, U6, U8 | `backend/modules/topics/delivery.py`, `backend/modules/export/classification.py`, `backend/modules/operations/recovery.py` |
| BR4.3 | Yes | U5, U6, U8 | `backend/modules/topics/control_lifecycle.py`, `backend/modules/export/lane.py`, `ops/src/docsuri_ops/backup_agent/writing.py` |
| BR5.1 | Yes | U5, U6, U8 | `backend/modules/topics/repository.py`, `backend/modules/export/approval_store.py`, `backend/u8_registry.py` |
| NFR1.3 | Yes | U6, U8 | `backend/modules/export/http.py`, `backend/modules/accounts/u8_control_policy.py` |
| NFR1.4 | Yes | U6, U8 | `backend/modules/export/control_lifecycle.py`, `ops/src/docsuri_ops/u8_platform/decisions.py` |
| NFR1.5 | Yes | U6 | `backend/modules/export/housekeeping_store.py` |
| NFR3.1 | Yes | U6, U8 | `backend/modules/export/token_vault.py`, `backend/modules/accounts/u8_verifier_key.py` |
| NFR3.2 | Yes | U6 | `backend/modules/export/token_keyring.py` |
| NFR3.3 | Yes | U6 | `backend/modules/export/key_commands.py` |
| NFR3.4 | Yes | U6 | `tests/u6_approved_export/component/test_token_exposure.py` |
| NFR3.5 | Yes | U6, U8 | `backend/modules/export/notion_session.py`, `ops/src/docsuri_ops/backup_agent/status.py` |
| NFR3.6 | Yes | U6, U8 | `backend/modules/export/classification.py`, `ops/src/docsuri_ops/arrangement/checklist.py` |
| NFR3.7 | Yes | U6 | `backend/modules/export/connection_store.py` |
| NFR3.8 | Yes | U6 | `backend/modules/export/notion_session.py` |
| NFR3.9 | Yes | U6, U8 | `backend/modules/export/notion_session.py`, `backend/log_events.py` |
| NFR4.4 | Yes | U6, U8 | `backend/modules/export/lane.py`, `backend/modules/operations/migration/parity.py` |
| NFR4.5 | Yes | U6 | `backend/modules/export/lane.py` |
| NFR4.6 | Yes | U6, U8 | `backend/modules/export/notion_adapter.py`, `backend/u8_workers.py` |
| NFR4.7 | Yes | U6 | `backend/modules/export/notion_adapter.py` |
| NFR4.8 | Yes | U6 | `backend/modules/export/lane_store.py` |
| NFR4.9 | Yes | U6 | `backend/modules/export/worker.py` |
| NFR4.10 | Yes | U6 | `backend/u6_policy.py` |
| NFR4.11 | Yes | U6 | `backend/modules/export/approval_store.py` |
| NFR6.2 | Yes | U6, U8 | `backend/u6_real_export.py`, `backend/modules/accounts/integrations/email_allowance.py` |
| NFR6.3 | Yes | U6 | `backend/modules/export/fake_notion.py` |
| NFR6.4 | Yes | U6 | `backend/modules/export/lane_store.py` |
| BR1.5 | Yes | U6, U8 | `backend/modules/export/notion_adapter.py`, `backend/u8_migrations.py` |
| BR1.6 | Yes | U6, U8 | `backend/modules/export/connection_store.py`, `tests/u8_service_operations_integration/operations/test_import_boundaries.py` |
| BR2.5 | Yes | U6, U8 | `backend/modules/export/preview_store.py`, `backend/modules/operations/lifecycle.py` |
| BR2.6 | Yes | U6, U8 | `backend/modules/export/housekeeping_store.py`, `backend/modules/operations/lifecycle.py` |
| BR3.5 | Yes | U6, U8 | `backend/modules/export/u6_schema.sql`, `backend/modules/operations/producers.py` |
| BR3.6 | Yes | U6, U8 | `backend/modules/export/approval_store.py`, `backend/modules/operations/producers.py` |
| BR3.7 | Yes | U6, U8 | `backend/modules/export/binding.py`, `backend/modules/operations/incidents.py` |
| BR4.4 | Yes | U6, U8 | `backend/modules/export/notion_adapter.py`, `backend/modules/operations/recovery.py` |
| BR4.5 | Yes | U6, U8 | `backend/modules/export/approval_store.py`, `backend/modules/operations/restore_checks.py` |
| BR4.6 | Yes | U6, U8 | `backend/modules/export/lane_store.py`, `backend/modules/operations/tombstones.py` |
| BR4.7 | Yes | U6, U8 | `backend/modules/export/lane.py`, `backend/modules/operations/recovery.py` |
| BR5.2 | Yes | U6, U8 | `backend/modules/export/approval_store.py`, `frontend/src/u8-shell/navigation.tsx` |
| BR6.1 | Yes | U6, U8 | `backend/modules/export/control_lifecycle.py`, `backend/u8_profile.py` |
| BR6.2 | Yes | U6, U8 | `backend/modules/export/u6_maintenance.sql`, `backend/modules/accounts/u8_verifier_key.py` |
| BR6.3 | Yes | U6, U8 | `backend/modules/export/control_lifecycle.py`, `ops/src/docsuri_ops/arrangement/paths.py` |
| BR6.4 | Yes | U6, U8 | `backend/modules/accounts/services/control_lifecycle.py`, `backend/production_boundary.py` |
| BR6.5 | Yes | U6 | `backend/modules/export/control_lifecycle.py` |
| BR7.1 | Yes | U6, U8 | `backend/modules/export/repository.py`, `backend/modules/accounts/integrations/identity_providers.py` |
| BR7.2 | Yes | U6, U8 | `backend/modules/export/notion_session.py`, `backend/modules/accounts/integrations/provider_gate.py` |
| BR8.1 | Yes | U6, U8 | `backend/u6_host.py`, `backend/modules/operations/migration/phases.py` |
| BR8.2 | Yes | U6, U8 | `backend/u6_real_export.py`, `backend/modules/accounts/services/v1_import.py` |
| BR8.3 | Yes | U6, U8 | `backend/u6_policy.py`, `backend/modules/operations/migration/identities.py` |
| NFR1.6 | **No** (`Deferred`) | U8 | none built in full: see below |
| NFR1.7 | Yes | U8 | `backend/local_browser.py` |
| NFR2.3 | Yes | U8 | `backend/modules/accounts/integrations/u8_digest_mail.py` |
| NFR3.10 | Yes | U8 | `ops/src/docsuri_ops/standing/healthchecks.py` |
| NFR3.11 | **No** (`Deferred`) | U8 | none built in full: see below |
| NFR3.12 | Yes | U8 | `backend/modules/operations/retained_copies.py` |
| NFR3.13 | Yes | U8 | `ops/src/docsuri_ops/backup_agent/disposal.py` |
| NFR3.14 | Yes | U8 | `backend/modules/operations/lifecycle.py` |
| NFR5.2 | Yes | U8 | `frontend/maintenance.html` |
| NFR7.1 | Yes | U8 | `ops/src/docsuri_ops/standing/availability.py` |
| NFR7.2 | **No** (`Deferred`) | U8 | none built in full: see below |
| NFR7.3 | **No** (`Deferred`) | U8 | none built in full: see below |
| NFR7.4 | Yes | U8 | `backend/u8_host.py` |
| NFR7.5 | Yes | U8 | `backend/maintenance_server.py` |
| NFR7.6 | Yes | U8 | `ops/src/docsuri_ops/standing/healthchecks.py` |
| NFR7.7 | Yes | U8 | `ops/src/docsuri_ops/backup_agent/cli.py` |
| NFR7.8 | Yes | U8 | `backend/modules/operations/restore_checks.py` |
| NFR7.9 | Yes | U8 | `backend/modules/operations/recovery.py` |
| NFR7.10 | Yes | U8 | `backend/modules/operations/recovery.py` |
| NFR7.11 | Yes | U8 | `ops/src/docsuri_ops/backup_agent/reading.py` |
| NFR7.12 | Yes | U8 | `backend/modules/accounts/integrations/provider_gate.py` |
| NFR7.13 | Yes | U8 | `backend/u8_capacity.py` |
| NFR7.14 | Yes | U8 | `ops/src/docsuri_ops/cutover/preconditions.py` |
| NFR7.15 | Yes | U8 | `ops/src/docsuri_ops/cutover/tool.py` |
| NFR7.16 | Yes | U8 | `backend/modules/accounts/services/v2_rollback_apply.py` |
| NFR7.17 | Yes | U8 | `backend/modules/operations/incidents.py` |
| NFR7.18 | Yes | U8 | `backend/u8_capacity.py` |
| NFR7.19 | Yes | U8 | `ops/src/docsuri_ops/isolation_check.py` |
| NFR8.1 | **No** (`Deferred`) | U8 | none built in full: see below |
| NFR8.2 | **No** (`Deferred`) | U8 | none built in full: see below |
| NFR8.3 | **No** (`Deferred`) | U8 | none built in full: see below |
| NFR8.4 | **No** (`Deferred`) | U8 | none built in full: see below |
| NFR8.5 | **No** (`Deferred`) | U8 | none built in full: see below |
| NFR8.6 | **No** (`Deferred`) | U8 | none built in full: see below |
| NFR8.7 | Yes | U8 | `backend/u8_model_lane.py` |
| NFR8.8 | Yes | U8 | `ops/src/docsuri_ops/migration/tool.py` |
| NFR8.9 | Yes | U8 | `ops/src/docsuri_ops/backup_agent/dumps.py` |
| NFR8.10 | Yes | U8 | `ops/src/docsuri_ops/isolation_check.py` |
| NFR8.11 | Yes | U8 | `scripts/verify_docsuri_u8.py` |
| NFR8.12 | Yes | U8 | `backend/u8_policy.py` |
| NFR8.13 | Yes | U8 | `backend/u8_capacity.py` |
| NFR8.14 | Yes | U8 | `ops/src/docsuri_ops/migration/disk_guard.py` |
| NFR8.15 | Yes | U8 | `ops/src/docsuri_ops/arrangement/paths.py` |
| NFR8.16 | Yes | U8 | `ops/src/docsuri_ops/backup_agent/status.py` |
| NFR8.17 | Yes | U8 | `ops/src/docsuri_ops/migration/inventory.py` |
| NFR8.18 | Yes | U8 | `backend/modules/operations/allowance.py` |
| NFR9.1 | Yes | U8 | `ops/src/docsuri_ops/standing/availability.py` |
| NFR9.2 | Yes | U8 | `backend/modules/operations/observations.py` |
| NFR9.3 | Yes | U8 | `backend/modules/operations/incidents.py` |
| NFR9.4 | Yes | U8 | `frontend/src/u8-operations/operations-view.tsx` |
| NFR9.5 | Yes | U8 | `frontend/src/u8-jobs/job-live-status.tsx` |
| NFR9.6 | Yes | U8 | `ops/src/docsuri_ops/standing/healthchecks.py` |
| NFR9.7 | Yes | U8 | `backend/modules/operations/producers.py` |
| NFR9.8 | **No** (`Deferred`) | U8 | none built in full: see below |
| NFR9.9 | Yes | U8 | `ops/src/docsuri_ops/isolation_check.py` |
| NFR9.10 | Yes | U8 | `scripts/verify_docsuri_u8.py` |
| NFR9.11 | Yes | U8 | `backend/request_context.py` |
| NFR9.12 | Yes | U8 | `ops/src/docsuri_ops/production_tool.py` |
| NFR9.13 | Yes | U8 | `ops/src/docsuri_ops/standing/availability.py` |
| BR1.7 | Yes | U8 | `backend/u8_main.py` |
| BR2.7 | Yes | U8 | `tests/u8_service_operations_integration/integration/test_lifecycle_manifest.py` |
| BR3.8 | Yes | U8 | `backend/modules/operations/http.py` |
| BR3.9 | Yes | U8 | `backend/log_events.py` |
| BR3.10 | Yes | U8 | `backend/log_events.py` |
| BR3.11 | Yes | U8 | `backend/u8_registry.py` |
| BR4.8 | Yes | U8 | `ops/src/docsuri_ops/backup_agent/dumps.py` |
| BR4.9 | Yes | U8 | `backend/modules/operations/recovery.py` |
| BR4.10 | Yes | U8 | `tests/u8_service_operations_integration/component/test_volume_retirement.py` |
| BR5.3 | Yes | U8 | `backend/u8_registry.py` |
| BR5.4 | Yes | U8 | `frontend/src/u8-jobs/jobs-view.tsx` |
| BR5.5 | Yes | U8 | `frontend/src/u8-shell/owner-boundary.ts` |
| BR5.6 | Yes | U8 | `frontend/privacy.html` |
| BR5.7 | Yes | U8 | `ops/src/docsuri_ops/cutover/tool.py` |
| BR5.8 | Yes | U8 | `frontend/e2e/u8-complete/accessibility.spec.ts` |
| BR5.9 | Yes | U8 | `backend/modules/operations/http.py` |
| BR6.6 | Yes | U8 | `backend/u8_capacity.py` |
| BR6.7 | Yes | U8 | `backend/u8_profile.py` |
| BR6.8 | Yes | U8 | `backend/modules/accounts/u8_control_policy.py` |
| BR6.9 | Yes | U8 | `ops/src/docsuri_ops/production_tool.py` |
| BR6.10 | Yes | U8 | `backend/modules/operations/ledger.py` |
| BR6.11 | **No** (`Deferred`) | U8 | none built in full: see below |
| BR6.12 | **No** (`Deferred`) | U8 | none built in full: see below |
| BR7.3 | **No** (`Deferred`) | U8 | none built in full: see below |
| BR7.4 | Yes | U8 | `backend/modules/accounts/integrations/email_allowance.py` |
| BR7.5 | Yes | U8 | `backend/modules/accounts/integrations/provider_gate.py` |
| BR7.6 | Yes | U8 | `backend/modules/accounts/integrations/u8_digest_mail.py` |
| BR7.7 | Yes | U8 | `backend/modules/summarization/model_runtime.py` |
| BR7.8 | **No** (`Deferred`) | U8 | none built in full: see below |
| BR8.4 | Yes | U8 | `backend/modules/operations/migration/phases.py` |
| BR8.5 | Yes | U8 | `backend/modules/accounts/services/v1_import.py` |
| BR8.6 | Yes | U8 | `backend/modules/accounts/services/first_sign_in.py` |
| BR8.7 | Yes | U8 | `backend/modules/corpus/paper_import.py` |
| BR8.8 | Yes | U8 | `backend/modules/operations/migration/phases.py` |
| BR8.9 | Yes | U8 | `backend/modules/operations/migration/misfits.py` |
| BR8.10 | Yes | U8 | `backend/modules/operations/migration/parity.py` |
| BR8.11 | Yes | U8 | `ops/src/docsuri_ops/migration/realm.py` |
| BR8.12 | Yes | U8 | `ops/src/docsuri_ops/migration/production.py` |
| BR8.13 | Yes | U8 | `backend/modules/accounts/services/v1_import.py` |
| BR8.14 | Yes | U8 | `backend/modules/operations/migration/identities.py` |
| BR8.15 | Yes | U8 | `ops/src/docsuri_ops/migration/tool.py` |
| BR9.1 | Yes | U8 | `ops/src/docsuri_ops/cutover/preconditions.py` |
| BR9.2 | Yes | U8 | `ops/src/docsuri_ops/cutover/preconditions.py` |
| BR9.3 | Yes | U8 | `tests/u8_service_operations_integration/component/test_soak_and_rehearsal.py` |
| BR9.4 | Yes | U8 | `backend/modules/operations/cutover.py` |
| BR9.5 | Yes | U8 | `backend/modules/operations/cutover.py` |
| BR9.6 | Yes | U8 | `frontend/src/u8-shell/moved-notice.tsx` |
| BR9.7 | Yes | U8 | `backend/modules/accounts/services/v2_rollback_apply.py` |
| BR9.8 | Yes | U8 | `ops/src/docsuri_ops/cutover/disposal.py` |
| BR9.9 | Yes | U8 | `ops/src/docsuri_ops/cutover/tool.py` |
| BR9.10 | Yes | U8 | `ops/src/docsuri_ops/u8_platform/u8_protocols.py` |
| BR9.11 | Yes | U8 | `ops/src/docsuri_ops/migration/inventory.py` |
| BR9.12 | Yes | U8 | `backend/modules/operations/retained_copies.py` |
| BR9.13 | Yes | U8 | `backend/modules/accounts/services/rollback_outcomes.py` |
| BR9.14 | Yes | U8 | `ops/src/docsuri_ops/u8_platform/decisions.py` |
| BR9.15 | Yes | U8 | `ops/src/docsuri_ops/u8_platform/platform_profile.py` |
| BR9.16 | Yes | U8 | `ops/src/docsuri_ops/u8_platform/v1_environment.py` |
| BR9.17 | Yes | U8 | `ops/src/docsuri_ops/backup_agent/disposal.py` |
| BR10.1 | Yes | U8 | `scripts/verify_docsuri_u8.py` |
| BR10.2 | Yes | U8 | `scripts/u8_tunnel_standin.py` |
| BR10.3 | Yes | U8 | `frontend/e2e/u8-complete/journeys.spec.ts` |
| BR10.4 | **No** (`Deferred`) | U8 | none built in full: see below |
| BR10.5 | **No** (`Deferred`) | U8 | none built in full: see below |
| BR10.6 | Yes | U8 | `frontend/e2e/u8-complete/accessibility.spec.ts` |
| BR10.7 | Yes | U8 | `ops/src/docsuri_ops/production_tool.py` |

## Uncovered IDs

| ID | Built and tested here | Left, and the stage that owns it |
|---|---|---|
| FR4.1 | Built and tested in this stage, Steps 5–8, 13–38 of U8's plan: the composed chain (backend/u8_migrations.py), the importers (backend/modules/accounts/services/v1_import.py, backend/modules/corpus/paper_import.py), AccountAccess's production policy and first sign-in (backend/modules/accounts/u8_control_policy.py, backend/modules/accounts/services/first_sign_in.py), the real providers and model evidence (backend/modules/accounts/integrations/identity_providers.py, backend/modules/summarization/model_runtime.py), production search and corpus limits (backend/modules/discovery/u8_search.py, backend/modules/corpus/limits.py), the backup agent (ops/src/docsuri_ops/backup_agent/cli.py), PlatformControl's bound operations and fixed programs (ops/src/docsuri_ops/u8_platform/u8_protocols.py, ops/bin/docsuri-production-tool), recovery and restore (backend/modules/operations/recovery.py), the migration tool (ops/src/docsuri_ops/migration/tool.py), the cutover (ops/src/docsuri_ops/cutover/tool.py), the standing job, isolation check, log rotation and maintenance server (ops/src/docsuri_ops/standing/main.py, ops/src/docsuri_ops/isolation_check.py, backend/maintenance_server.py) and the installer, release command and production environment tool (ops/src/docsuri_ops/arrangement/installer.py, ops/src/docsuri_ops/release.py, ops/src/docsuri_ops/production_tool.py) | the continuous run on the real arrangement with real accounts and real papers — the in-person installer verification, the migration dry runs on real v1 data, the soak, the switch and the rollback window — belongs to Environment Provisioning, Deployment Execution and the Operation stages (plan '## Completion and evidence boundaries'); the macOS CI job has never run U8's arrangement tests and U8's workflows have not run on GitHub (code summary '## Open items and handoffs'). Owner: Environment Provisioning, Deployment Execution and the Operation stages |
| FR4.2 | Built in this stage, Steps 15–16, 43–45 of U8's plan: observations, readiness and incidents (backend/modules/operations/observations.py, backend/modules/operations/readiness.py, backend/modules/operations/incidents.py), the composed realm's VerificationRun and performance phases (scripts/verify_docsuri_u8.py), the CI and release workflows (.github/workflows/u8-complete-verification.yml, .github/workflows/ci.yml, .github/workflows/release.yml, scripts/u8_release_guard.py) and the four U8 runbooks in this record directory | the real evidence over the complete application in its real operating mode is produced by Build and Test, CI Pipeline, Deployment Pipeline, Deployment Execution, Performance Validation and the Operation stages (plan '## Completion and evidence boundaries'); U8's workflows have not yet run on GitHub (code summary '## Open items and handoffs'). Owner: Build and Test (this stage, where U8's scope floor is Not Met in the sixth run), CI Pipeline, Deployment Pipeline, Deployment Execution, Performance Validation and the Operation stages |
| NFR1.6 | Steps 27–28, 37–38 of U8's plan: the fixed programs (ops/src/docsuri_ops/u8_platform/fixed.py, ops/bin/docsuri-service-start; tests/u8_service_operations_integration/operations/test_fixed_programs.py) | the sudoers template lint under visudo (tests/u8_service_operations_integration/arrangement/test_template_lint.py) runs in the macOS CI job (ci.yml macos-filesystem), which has never run U8's arrangement tests (code summary '## Open items and handoffs'); the in-person password checks (D4) run at the installation. Owner: CI Pipeline (the macOS job's visudo lint) and Environment Provisioning (the in-person password checks) |
| NFR3.11 | Steps 37–38, 44 of U8's plan: the pinned runtimes with their publisher checksums and the frozen lockfile install (ops/src/docsuri_ops/arrangement/runtimes.py, ops/src/docsuri_ops/release.py; tests/u8_service_operations_integration/operations/test_release_install.py) | the clean-clone release-environment install and its otool -L check (tests/u8_service_operations_integration/arrangement/test_release_environment.py) run in the macOS CI job (ci.yml macos-filesystem), which has never run U8's arrangement tests (code summary '## Open items and handoffs'), and U8's workflows have not run on GitHub. Owner: CI Pipeline (the macOS job's clean-clone release install and its `otool -L` check) |
| NFR7.2 | Steps 11–12, 37–38 of U8's plan: every long-running job rendered with KeepAlive (ops/src/docsuri_ops/arrangement/templates/launch-jobs.json, ops/src/docsuri_ops/arrangement/render.py; tests/u8_service_operations_integration/operations/test_templates.py) | the launch-job template lint under plutil (tests/u8_service_operations_integration/arrangement/test_template_lint.py) runs in the macOS CI job (ci.yml macos-filesystem), which has never run U8's arrangement tests (code summary '## Open items and handoffs'); launchd's real restart is proved at the installation. Owner: CI Pipeline (the macOS job's plutil lint) and Environment Provisioning (launchd's real restart) |
| NFR7.3 | Steps 35–38 of U8's plan: the root jobs, the volume unlock and the start order (ops/src/docsuri_ops/backup_unlock.py, ops/src/docsuri_ops/standing/main.py; tests/u8_service_operations_integration/operations/test_root_jobs.py) | after an authorized restart every job runs and the volume is unlocked before anyone logs in, ready within 3 minutes, proved at Workflow 20 step 10 at Environment Provisioning per the plan's '## Completion and evidence boundaries' table. Owner: Environment Provisioning (Workflow 20 step 10) |
| NFR8.1 | Steps 15–16, 39–40, 43 of U8's plan: the latency summaries per measure (backend/modules/operations/observations.py; tests/u8_service_operations_integration/component/test_latency_summaries.py) and the composed realm's performance phase (scripts/verify_docsuri_u8.py) | NFR8.1–NFR8.6 at the production scale on this Mac are measured by the performance phase of each install and by the soak, at Deployment Execution and Performance Validation (plan '## Completion and evidence boundaries'). Owner: Deployment Execution and Performance Validation (each install's performance phase and the soak) |
| NFR8.2 | Steps 41–44 of U8's plan: the workspace build with its first-load budget and the compressed, immutable static files (scripts/u8_build_workspace.py, backend/u8_host.py; frontend/e2e/u8-complete/journeys.spec.ts) | the 2 s first load and 1 s navigation through the public address at production scale are measured by the performance phase of each install and the soak, at Deployment Execution and Performance Validation. Owner: Deployment Execution and Performance Validation (each install's performance phase and the soak) |
| NFR8.3 | Steps 7–10, 43 of U8's plan: the host's server timing per route class with identifiers only (backend/u8_host.py, backend/request_context.py; tests/u8_service_operations_integration/integration/test_host_routes.py) | the 500 ms target at production scale is measured by the performance phase of each install and the soak, at Deployment Execution and Performance Validation. Owner: Deployment Execution and Performance Validation (each install's performance phase and the soak) |
| NFR8.4 | Steps 7–8, 21–24, 43 of U8's plan: production search with the local embedding of the query (backend/modules/discovery/u8_search.py, backend/modules/discovery/local_embedding.py; tests/u8_service_operations_integration/integration/test_signed_in_search.py) | the 3 s target at the production corpus is measured by the performance phase of each install and the soak, at Deployment Execution and Performance Validation. Owner: Deployment Execution and Performance Validation (each install's performance phase and the soak) |
| NFR8.5 | Steps 39–40, 43 of U8's plan: the routes and the composed realm's performance phase (backend/u8_host.py, scripts/verify_docsuri_u8.py) | the production-scale measure is taken by the performance phase of each install and the soak, at Deployment Execution and Performance Validation. Owner: Deployment Execution and Performance Validation (each install's performance phase and the soak) |
| NFR8.6 | Steps 11–12, 43 of U8's plan: the start checks and readiness after a restart (backend/u8_host.py; tests/u8_service_operations_integration/integration/test_start_checks.py) | start to ready under 3 minutes after a real restart, PostgreSQL's own start included, is measured at Environment Provisioning, from the standing job's start record at the installation's authorized restart (Workflow 20 step 10), and at Deployment Execution, from the cutover runbook's restart rehearsal of v1. No install performance phase measures it, because that phase restarts nothing, though U8's traceability.json names it. Owner: Environment Provisioning (Workflow 20 step 10) and Deployment Execution (v1's restart rehearsal) |
| NFR9.8 | Steps 9–10, 35–36 of U8's plan: the production log shape and the rotation job (backend/log_events.py, ops/src/docsuri_ops/logrotate.py; tests/u8_service_operations_integration/operations/test_logrotate_rules.py) | the real-tool rotation tests (tests/u8_service_operations_integration/arrangement/test_logrotate.py) run in the macOS CI job (ci.yml macos-filesystem), which has never run U8's arrangement tests (code summary '## Open items and handoffs'). Owner: CI Pipeline (the macOS job's real-tool rotation tests) |
| BR6.11 | Steps 11–12, 15–16, 21–22, 35–38 of U8's plan: the accounts, launch jobs, packet filter, sudo rules and root-owned folders the installer renders and verifies (ops/src/docsuri_ops/arrangement/installer.py, ops/src/docsuri_ops/arrangement/render.py, ops/src/docsuri_ops/arrangement/verify.py; tests/u8_service_operations_integration/operations/test_installer.py) | the arrangement on the real Mac is proved by the installer's verification at Environment Provisioning per the plan's '## Completion and evidence boundaries' table (the NFR1.5, NFR3.3, NFR3.7 and NFR3.8 rows), and the template lint under visudo, plutil and pfctl runs in the macOS CI job (ci.yml macos-filesystem), which has never run U8's arrangement tests (code summary '## Open items and handoffs'). Owner: Environment Provisioning (the installer's verification) and CI Pipeline (the macOS job's template lint) |
| BR6.12 | Steps 15–16, 27–28, 31–32, 35–36 of U8's plan: the read-only isolation check, its planned-stop record and its evidence folder (ops/src/docsuri_ops/isolation_check.py, ops/src/docsuri_ops/isolation_macos.py; tests/u8_service_operations_integration/operations/test_isolation_check.py) | the check's real run every renewal interval, as root under the scheduler's grant, is proved at Workflow 20 step 11 at Environment Provisioning per the plan's '## Completion and evidence boundaries' table. Owner: Environment Provisioning (Workflow 20 step 11) |
| BR7.3 | Steps 21–22, 33–34 of U8's plan: the held first effect, its recorded preview digest and the maintainer's approval (backend/modules/operations/provider_activation.py, ops/src/docsuri_ops/cutover/decide.py; tests/u8_service_operations_integration/integration/test_first_effects.py) | the first email and the first export on the maintainer's decisions run at Deployment Execution's maintainer-only window (plan '## Completion and evidence boundaries'). Owner: Deployment Execution (the first email and export in the maintainer-only window) |
| BR7.8 | Steps 21–22, 33–34 of U8's plan: the real Google and ORCID adapters and the cutover's maintainer-only window (backend/modules/accounts/integrations/identity_providers.py, backend/modules/operations/cutover.py; tests/u8_service_operations_integration/component/test_identity_providers.py) | real Google and ORCID sign-in through the public address is verified by the maintainer at Deployment Execution's maintainer-only window (plan '## Completion and evidence boundaries'). Owner: Deployment Execution (real Google and ORCID sign-in in the maintainer-only window) |
| BR10.4 | Step 44 of U8's plan: the complete verification's own CI lane beside the per-unit runners (.github/workflows/u8-complete-verification.yml; tests/u8_service_operations_integration/operations/test_u8_tool.py reads it) | the lane has not run on GitHub (code summary '## Open items and handoffs'). Owner: CI Pipeline (the lane's first run on GitHub) |
| BR10.5 | Steps 37–38, 43–44 of U8's plan: the release guard that refuses a readiness or release claim without passing complete evidence for the exact commit (scripts/u8_release_guard.py, ops/src/docsuri_ops/release.py; tests/u8_service_operations_integration/operations/test_release_guard.py) | the first release — main's one-off push, the v2.0.0 tag through custom_tag, the guard and branch protection's required checks reporting — runs at CI Pipeline and Deployment Pipeline (plan '## Completion and evidence boundaries'); U8's workflows have not run on GitHub. Owner: CI Pipeline and Deployment Pipeline (the first release) |

Each owning stage other than Build and Test is in this workflow's plan and has not started yet.
