-- Ops exposes only aggregate footprint; no directory names or arbitrary paths.
-- The migration runner grants pg_ls_waldir() to this non-login schema owner.
CREATE FUNCTION operations.capacity_footprint()
RETURNS TABLE(database_bytes bigint,wal_bytes bigint)
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog AS $$
  SELECT pg_database_size(current_database()),coalesce(sum(size),0)::bigint
    FROM pg_ls_waldir()
    WHERE current_database()='docsuri_u2'
$$;
REVOKE ALL ON FUNCTION operations.capacity_footprint() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION operations.capacity_footprint() TO docsuri_operations;
