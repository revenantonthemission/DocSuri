-- Replaces backend/modules/accounts/u5_lifecycle_tables.sql in U8's composed chain (BR1.5).
-- U5's file mirrors u2_controls.sql verbatim: the account's lifecycle_revision, the
-- lifecycle request and scope tables, their owner page index and their grant. On the
-- composed chain u2_controls.sql has already created all of them, so U5's file would
-- fail. What U5's file gave its callers is exactly U2's definition; this file proves
-- that definition is in place, fails closed if it is not, and repeats U5's grant.
-- U5's file stays applied, unchanged, in U5's and U6's own realms.
DO $$
DECLARE missing text;
BEGIN
  SELECT string_agg(expected.table_name || '.' || expected.column_name, ', ')
    INTO missing
    FROM (VALUES
      ('account','lifecycle_revision'),
      ('lifecycle_request','revision'), ('lifecycle_request','action'),
      ('lifecycle_request','policy_ref'), ('lifecycle_request','manifest_revision'),
      ('lifecycle_request','manifest'), ('lifecycle_request','disposition'),
      ('lifecycle_request','status_generation'),
      ('lifecycle_scope','participant'), ('lifecycle_scope','scope'),
      ('lifecycle_scope','generation'), ('lifecycle_scope','lease_until'),
      ('lifecycle_scope','attempts'), ('lifecycle_scope','evidence_ref')
    ) AS expected(table_name, column_name)
    WHERE NOT EXISTS (
      SELECT 1 FROM information_schema.columns c
       WHERE c.table_schema='accounts' AND c.table_name=expected.table_name
         AND c.column_name=expected.column_name);
  IF missing IS NOT NULL THEN
    RAISE EXCEPTION 'U2 lifecycle definition missing: %', missing USING ERRCODE='42P01';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_indexes
                  WHERE schemaname='accounts' AND indexname='lifecycle_owner_page') THEN
    RAISE EXCEPTION 'U2 lifecycle owner page index missing' USING ERRCODE='42P01';
  END IF;
END $$;
GRANT SELECT,INSERT,UPDATE ON accounts.lifecycle_request,accounts.lifecycle_scope TO docsuri_accounts;
