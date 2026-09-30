-- 014_add_purge_version.sql
-- BR-PURGE-07: optimistic locking on purge state transitions. The existing row-level writes
-- (mark_deletion_purged/increment_attempts/mark_deletion_failed) update by PK but have no
-- version check; a second sweep could overwrite a transition. Add version (default 1) and
-- require it on future guarded updates.
ALTER TABLE account_deletions
  ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
-- Ensure existing rows have version>=1 (default already set on insert, backfill just in case)
UPDATE account_deletions SET version = 1 WHERE version IS NULL;
