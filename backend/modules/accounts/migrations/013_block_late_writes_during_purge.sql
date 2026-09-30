-- 013_block_late_writes_during_purge.sql
-- F04: a DEACTIVATED(유예 중) owner must not accumulate new first-party rows. Without this an
-- owner-scoped write that lands after the purge job read its due-deletion list (or after the DB
-- cascade ran but before S3/backup GC finished) survives the purge, leaving personal data behind
-- in a table the next sweep no longer considers — the account is PURGED yet its rows are not.
--
-- The guard is a BEFORE INSERT/UPDATE trigger that rejects the write when the owning account is not
-- ACTIVE. It is deliberately stricter than the purge state machine: any non-ACTIVE state
-- (DEACTIVATED, PURGE_FAILED, or already purged/absent) blocks new owner data. Restoring an owner
-- is an explicit reactivate() that returns the account to ACTIVE, which re-opens writes — so this
-- never needs a manual unlock.
--
-- Idempotent: DROP TRIGGER IF EXISTS before CREATE, and the table list is fixed. Re-running is a
-- no-op.
CREATE OR REPLACE FUNCTION accounts_block_owner_write_when_inactive() RETURNS trigger AS $$
DECLARE owner_id text;
BEGIN
    -- Prefer the conventional owner column; fall back for tables that name it differently
    -- (e.g. user_glossary.user_id).
    IF TG_ARGV[0] IS NULL OR TG_ARGV[0] = '' THEN
        RETURN NEW;
    END IF;
    -- NEW is a record; cast to jsonb so the owner column can be read by name without the
    -- identifier being interpolated into a value position (a bare SELECT ($1).col binds a
    -- *parameter*, and a trigger has no parameters to bind).
    owner_id := to_jsonb(NEW) ->> TG_ARGV[0];
    IF owner_id IS NULL THEN
        RETURN NEW;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM accounts WHERE id = owner_id AND status = 'ACTIVE') THEN
        RAISE EXCEPTION
            'owner_write_blocked: account % is not ACTIVE; owner-scoped writes are refused while '
            'the account is deactivated or purged', owner_id
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    spec text;
    parts text[];
    tbl text;
    col text;
BEGIN
    FOREACH spec IN ARRAY ARRAY[
        'research_messages:owner_id',
        'research_jobs:owner_id',
        'novelty_messages:owner_id',
        'novelty_progress_events:owner_id',
        'novelty_artifacts:owner_id',
        'novelty_notion_exports:owner_id',
        'novelty_notion_connections:owner_id',
        'novelty_jobs:owner_id',
        'saved_searches:owner_id',
        'library_items:owner_id',
        'search_history:owner_id',
        'user_behavior_events:owner_id',
        'user_interest_profiles:owner_id',
        'personalization_settings:owner_id',
        'mypage_subscriptions:owner_id',
        'user_glossary:user_id'
    ] LOOP
        parts := string_to_array(spec, ':');
        tbl := parts[1];
        col := parts[2];
        -- A table absent from this deployment is skipped rather than failing the migration, so the
        -- same file applies to deployments with a different module set (mirrors the purge
        -- backstop's runtime table whitelist).
        IF to_regclass('public.' || tbl) IS NULL THEN
            CONTINUE;
        END IF;
        EXECUTE format('DROP TRIGGER IF EXISTS trg_block_owner_write_%s ON public.%I', tbl, tbl);
        EXECUTE format(
            'CREATE TRIGGER trg_block_owner_write_%s BEFORE INSERT OR UPDATE ON public.%I '
            'FOR EACH ROW EXECUTE FUNCTION accounts_block_owner_write_when_inactive(%L)',
            tbl, tbl, col
        );
    END LOOP;
END;
$$;

-- Advisory lock for the purge sweep. Two concurrent purge_job runs (overlapping cron, or the
-- launchd timer firing while a manual run is still going) would otherwise both read the same due
-- list and race on the same account: one purges while the other is mid-cascade, and the loser's
-- commit can resurrect partially-deleted state or double-fire the S3/backup-GC legs.
--
-- The lock is transaction-scoped (xact lock) so it releases on COMMIT or ROLLBACK with no
-- sweeper-process to leak. try_advisory_lock is non-blocking: if another sweep holds it, this one
-- stands down for the cycle instead of blocking every subsequent purge behind a stuck run. The
-- caller treats "lock not acquired" as zero-purged and exits cleanly.
CREATE OR REPLACE FUNCTION accounts_try_purge_lock() RETURNS boolean AS $$
BEGIN
    RETURN pg_try_advisory_xact_lock(hashtext('docsuri:accounts:purge-sweep'));
END;
$$ LANGUAGE plpgsql;
