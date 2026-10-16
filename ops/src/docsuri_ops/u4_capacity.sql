-- U4 amendment: bind shared aggregate capacity observation to docsuri_u4.
-- The runner grants WAL observation and database CONNECT only to this
-- non-login operations schema owner. Runtime receives the aggregate function.
CREATE OR REPLACE FUNCTION operations.capacity_footprint()
RETURNS TABLE(database_bytes bigint,wal_bytes bigint)
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog AS $$
  SELECT pg_database_size(current_database()),coalesce(sum(size),0)::bigint
    FROM pg_ls_waldir()
    WHERE current_database()='docsuri_u4'
$$;
REVOKE ALL ON FUNCTION operations.capacity_footprint() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION operations.capacity_footprint() TO docsuri_operations;
