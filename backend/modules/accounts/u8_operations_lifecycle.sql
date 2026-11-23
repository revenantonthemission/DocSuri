-- U8 (BR2.5, BR2.6, U8 plan Step 17): AccountAccess admits ServiceOperations as a
-- lifecycle participant, a correction added after u8_accounts.sql; it replaces no
-- file. The guard already maps ServiceOperations -> docsuri_operations and
-- u2_lifecycle_action.sql grants that login EXECUTE on lifecycle_effect_action; the
-- login also needs USAGE on this schema to reach the function, as u5_lifecycle_guard.sql
-- and u6_lifecycle_guard.sql grant it to the topics and export logins.
GRANT USAGE ON SCHEMA accounts TO docsuri_operations;
