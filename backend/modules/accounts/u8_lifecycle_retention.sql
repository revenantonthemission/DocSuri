-- U8 (your decision of 2026-10-22; BR2.5, A3): AccountAccess keeps, beside a lifecycle
-- scope's evidence, the latest date by which a part retained by policy is gone, as the
-- participant reported it (ServiceOperations' backups scope, with the reason key
-- backups-retained-until-disposal), so the erase's status shows that part as retained by
-- policy until that date. A correction added after u8_operations_lifecycle.sql; it
-- replaces no file. Null for every existing row and for every scope that reports no
-- date; earlier realms, whose chains do not include this file, never read or write it.
ALTER TABLE accounts.lifecycle_scope ADD COLUMN retained_until timestamptz;
ALTER TABLE accounts.lifecycle_scope ADD CONSTRAINT lifecycle_scope_retained_until_check
  CHECK (retained_until IS NULL OR disposition = 'complete');
