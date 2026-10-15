# U2 least-privilege and restriction evidence

Observed 2026-10-14 against the owned synthetic realm (`docsuri_u2`, run `docsuri-u2-c274e71798431965`). The migrate phase created every role and constraint; this record verifies the live restriction state needed by the quarantined restore protocol. It is configuration evidence, not behavior success.

## Role attributes (pg_roles)

- Eight schema owners (`docsuri_<owner>_owner`): `NOLOGIN`, `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOINHERIT`, `NOBYPASSRLS`. They hold `UC` on their own schema and execute the `SECURITY DEFINER` guarded functions.
- Eight runtime logins (`docsuri_<owner>`): `LOGIN`, `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOINHERIT`, `NOBYPASSRLS`, `CONNECTION LIMIT 2`, scram password per run manifest. `docsuri_operations_owner` additionally receives `CONNECT` and, only when the `u2_capacity` migration applies, `EXECUTE` on `pg_catalog.pg_ls_waldir()` — never an application login role.

## Cross-owner isolation checks

| Check (as postgres) | Observed |
|---|---|
| `has_schema_privilege('docsuri_accounts','usage','USAGE')` | false |
| `has_table_privilege('docsuri_usage','accounts.receipt','SELECT')` | false |
| `has_table_privilege('docsuri_usage','usage.receipt','DELETE')` | false |
| `has_table_privilege('docsuri_usage','usage.rejected_operation','DELETE')` | false (append-only rejection ledger) |
| Database ACL | no `PUBLIC`/`=...` entry; only `CONNECT` to postgres and the eight runtime roles plus the operations owner |
| `public` schema ACL | `USAGE` only to the eight runtime roles; `accounts`/`usage` schemas list only their owner and the narrow cross-owner grants |

## Migration identity and compatibility

`public.docsuri_local_identity` retains the run id and a per-file SHA-256 for every base schema and applied amendment (currently including `u2_capacity.sql`, `u2_controls.sql`, `u2_restore*.sql`). The runner refuses to apply a changed previously-applied file (`"applied U2 migration changed; add a new ordered migration"`), and refuses to migrate while the application listener is up. Migration DDL runs as the schema owner under `SET LOCAL ROLE`, never as postgres on application schemas.

## Finite constraints and indexes (representative, verified live)

- Accounts: `control_proof_proof_hash_key` unique, `challenge_proof_hash_key` unique, `identity_link_provider_subject_key` unique (provider, subject) and `identity_link_account_id_provider_key` unique per account, `identity_flow_state_hash_key` unique, `mfa_enrollment_delivery_hash_key` unique, `mfa_enrollment_state_check` (`inactive|active|invalidated`), `lifecycle_scope_check` (complete requires evidence), `lifecycle_scope_attempts_check` ≤ 3, `reset_confirmation_account_id_prepare_key_key` unique, `account_lifecycle_state_check`.
- Library: `history_captured_generation_check`, `history_boundary_generation_check`, `history_boundary_admission_cutoff_check`, `restriction_disposition_check`.
- Personalization: `reset_responsibility_status_revision_check` (`status_revision > 0`, per-reset monotonic status revision distinct from the settings revision), `reset_responsibility_account_id_input_boundary_key` unique, `reset_scope_check` (complete requires evidence), `settings_appearance_check`.
- Usage: `entitlement_allocation_check` 0–4, `entitlement_policy_check` (U1 and U2 policies only), `reservation_check` (`reserved` ⇔ no settlement key), `reservation_disposition_check`, `reservation_operation_generation_check`, `reservation_quantity_check` 1–3.
- Assistance: `admission_disposition_check` (`open|accepted|rejected`), `admission_generation_check`, `admission_quantity_check`, `admission_reservation_id_key`/`job_reservation_id_key` unique.
- Restore: `operations.restore_checkpoint_check` requires a null previous digest only for sequence 1 and a 64-hex digest beyond it; owner checkpoint tables enforce `sequence > 0`.

## Restore restriction binding

The quarantine protocol consumes the exports above: AccountAccess exports lifecycle state/revisions and credential digests (no credentials), each owner exports its current restrictions, and Assistance/Discovery extend them with `erasedOwner` markers. The restore database is `docsuri_u2_restore`, reachable only as `postgres` inside the owned container; the reconcilers refuse any other database or session user, and the coordinator drops it only through its explicit owned cleanup. Older backups cannot resurrect old credentials, sessions, proofs, links, MFA state or acceptance — verified by the actual older-backup rehearsal in `operations-verification.md`.
