-- Replaces ops/src/docsuri_ops/u3_capacity_v2.sql in U8's composed chain, last in the
-- chain, with A10's one capacity definition (BR1.5, BR6.6, scalability-design § 3.1).
-- u2_capacity.sql already creates operations.capacity_footprint(), so U3's plain CREATE
-- FUNCTION would fail; the other capacity files are CREATE OR REPLACE or use their own
-- name and stay in the chain. The earlier definitions count WAL only for one database
-- name (docsuri_u2, docsuri_u3, docsuri_u4). A10's footprint is the current database's
-- size plus the WAL of the whole instance, for any database name: production, a
-- rehearsal database or the composed realm. The runner grants pg_ls_waldir() and
-- CONNECT to this non-login schema owner; runtime receives only the aggregate function.
-- U3's file stays applied, unchanged, in U3-U6's own realms.
CREATE OR REPLACE FUNCTION operations.capacity_footprint()
RETURNS TABLE(database_bytes bigint,wal_bytes bigint)
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog AS $$
  SELECT pg_database_size(current_database()),
         coalesce((SELECT sum(size) FROM pg_ls_waldir()),0)::bigint
$$;
REVOKE ALL ON FUNCTION operations.capacity_footprint() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION operations.capacity_footprint() TO docsuri_operations;
